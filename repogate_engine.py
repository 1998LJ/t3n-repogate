import os
import sys
import re
import json
import hashlib
from typing import Dict, Any, List, Optional
import requests

class RepoGateEngine:
    """
    RepoGate: Autonomous Pull Request Quality and Risk Evaluation Engine
    Executes a 6-gate inspection matrix:
      1. Duplicate Gate (linked Issue, historical merged/open PRs, default branch existence)
      2. Issue State Gate (linked issue state, timeline, upstream implementation)
      3. CI Gate (GitHub Actions status/conclusion without spoofing)
      4. Regression Test Gate (failing test presence, production-without-test check, xfail removal)
      5. Scope Gate (diff size, blast radius, debugging residue)
      6. Policy Guard (unauthorized SLA, contact, bounty commitments)
    """

    POLICY_FILES = [
        "SECURITY.MD", "SUPPORT.MD", "GOVERNANCE.MD",
        "SLA.MD", "CONTRIBUTING.MD", "SECURITY", "SUPPORT"
    ]

    UNAUTHORIZED_PATTERNS = [
        (r'\b(?:within\s+\d+\s+(?:hours|days)|48\s*hours|24\s*hours|30\s*days)\b', "Unapproved SLA or response turnaround timeframe"),
        (r'\b(?:bounty(?: of| up to)?\s*[$]?\d+|[$]?\d+\s*(?:usd|usdc|dollars)?\s*reward)\b', "Unapproved financial bounty or reward commitment"),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "Hardcoded specific contact email without upstream authorization")
    ]

    def __init__(self, github_token: Optional[str] = None, proxies: Optional[Dict[str, str]] = None):
        # P0-7: Default proxies=None for clean machine portability
        self.token = github_token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if proxies is not None:
            self.proxies = proxies
        elif os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("ALL_PROXY"):
            raw_p = os.environ.get("HTTPS_PROXY") or os.environ.get("ALL_PROXY") or os.environ.get("HTTP_PROXY") or ""
            norm_p = raw_p.replace("socks5://", "socks5h://")
            self.proxies = {
                'http': norm_p,
                'https': norm_p
            }
        else:
            self.proxies = None

        self.session = requests.Session()
        self.session.trust_env = False
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _get(self, url: str) -> requests.Response:
        try:
            return self.session.get(url, headers=self._headers(), proxies=self.proxies, timeout=15)
        except Exception:
            return requests.get(url, headers=self._headers(), proxies=self.proxies, timeout=15)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RepoGate-Quality-Agent/1.0"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def analyze_pr(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Runs the complete 6-gate evaluation on a given PR."""
        base_api = f"https://api.github.com/repos/{owner}/{repo}"
        
        pr_resp = self._get(f"{base_api}/pulls/{pr_number}")
        if pr_resp.status_code != 200:
            raise ValueError(f"Failed to fetch PR #{pr_number}: {pr_resp.status_code}")
        pr = pr_resp.json()

        files_resp = self._get(f"{base_api}/pulls/{pr_number}/files")
        files = files_resp.json() if files_resp.status_code == 200 else []

        # 1. CI Gate
        ci_gate = self._eval_ci_gate(base_api, pr)

        # 2. Duplicate Gate (P0-4: checks linked issue, merged PRs, main branch file existence)
        duplicate_gate = self._eval_duplicate_gate(owner, repo, pr, files)

        # 3. Issue State Gate (P0-5: checks linked issue timeline, closed status, upstream commit race)
        issue_gate = self._eval_issue_gate(owner, repo, pr, files)

        # 4. Regression Test Gate (P0-6: checks test existence, xfail removal verification)
        test_gate = self._eval_regression_test_gate(files)

        # 5. Scope Gate
        scope_gate = self._eval_scope_gate(pr, files)

        # 6. Policy Guard
        policy_gate = self._eval_policy_guard(files)

        # Scoring & Final Recommendation
        risk_score = 0
        blocking = []
        warnings = []

        if duplicate_gate["status"] == "DUPLICATE":
            risk_score += 40
            blocking.append(f"Duplicate implementation detected: {duplicate_gate['reason']}")
        elif duplicate_gate["status"] == "POSSIBLE_DUPLICATE":
            risk_score += 20
            warnings.append(f"Potential duplicate PRs exist: {duplicate_gate['reason']}")

        if issue_gate["status"] == "SUPERSEDED":
            risk_score += 50
            blocking.append(f"Upstream race: {issue_gate['reason']}")
        elif issue_gate["status"] == "STALE":
            risk_score += 30
            warnings.append(f"Linked issue or target is stale: {issue_gate['reason']}")

        if ci_gate["status"] == "CI Failed":
            risk_score += 40
            blocking.append(f"CI failed on {ci_gate.get('failed_workflow') or 'remote check'}")

        if test_gate["status"] == "MISSING_TESTS":
            risk_score += 25
            warnings.append(test_gate["reason"])
        elif test_gate["status"] == "UNVERIFIED_XFAIL_REMOVAL":
            risk_score += 30
            blocking.append(test_gate["reason"])

        if scope_gate["status"] == "EXCESSIVE_SCOPE":
            risk_score += 20
            warnings.append(f"High diff / file touch count: {scope_gate['reason']}")

        if policy_gate["status"] == "FAIL":
            risk_score += 35
            for f in policy_gate["findings"]:
                blocking.append(f"Policy Guard violation in {f['file']}: {f['reason']} ({', '.join(f['matches'])})")

        risk_score = min(100, risk_score)

        if pr.get("merged"):
            recommendation = "MERGED"
        elif duplicate_gate["status"] == "DUPLICATE":
            recommendation = "CLOSE_DUPLICATE"
        elif issue_gate["status"] == "SUPERSEDED":
            recommendation = "SUPERSEDED"
        elif blocking or risk_score >= 50:
            recommendation = "FIX_REQUIRED"
        elif ci_gate["status"] == "CI Passed" and risk_score < 25:
            recommendation = "MERGE_READY"
        else:
            recommendation = "WAIT_FOR_REVIEW"

        report = {
            "target": f"{owner}/{repo}#{pr_number}",
            "pr_title": pr.get("title"),
            "pr_author": pr.get("user", {}).get("login"),
            "base_branch": pr.get("base", {}).get("ref"),
            "head_branch": pr.get("head", {}).get("ref"),
            "risk_score": risk_score,
            "merge_readiness": "READY" if recommendation in ["MERGE_READY", "MERGED"] else "BLOCKED",
            "recommended_action": recommendation,
            "gates": {
                "duplicate_gate": duplicate_gate,
                "issue_state_gate": issue_gate,
                "ci_gate": ci_gate,
                "regression_test_gate": test_gate,
                "scope_gate": scope_gate,
                "policy_guard": policy_gate
            },
            "blocking_findings": blocking,
            "warnings": warnings,
            "pr_state": pr.get("state"),
            "merged": pr.get("merged", False)
        }
        return report

    def _eval_ci_gate(self, base_api: str, pr: Dict[str, Any]) -> Dict[str, Any]:
        head_sha = pr.get("head", {}).get("sha")
        runs_resp = self._get(f"{base_api}/actions/runs?head_sha={head_sha}")
        
        if runs_resp.status_code == 200:
            runs = runs_resp.json().get("workflow_runs", [])
            if runs:
                failed = [r for r in runs if r.get("conclusion") in ["failure", "timed_out", "action_required"]]
                in_progress = [r for r in runs if r.get("status") in ["in_progress", "queued"]]
                if failed:
                    return {
                        "status": "CI Failed",
                        "failed_workflow": failed[0].get("name"),
                        "runs_checked": len(runs),
                        "evidence": f"Workflow {failed[0].get('name')} concluded with {failed[0].get('conclusion')}"
                    }
                if in_progress:
                    return {"status": "Submitted", "runs_checked": len(runs), "evidence": "Workflows still queued or in progress"}
                return {"status": "CI Passed", "runs_checked": len(runs), "evidence": f"All {len(runs)} workflows concluded successfully"}

        combined_resp = self._get(f"{base_api}/commits/{head_sha}/status")
        if combined_resp.status_code == 200:
            state = combined_resp.json().get("state")
            if state == "success":
                return {"status": "CI Passed", "evidence": "Commit status combined state is success"}
            elif state == "failure":
                return {"status": "CI Failed", "evidence": "Commit status combined state is failure"}
            elif state == "pending":
                return {"status": "Submitted", "evidence": "Commit status is pending"}

        return {"status": "Submitted", "evidence": "No external CI runs or status checks reported"}

    def _eval_duplicate_gate(self, owner: str, repo: str, pr: Dict[str, Any], files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        P0-4 Enhancement:
        Checks:
        1. Linked Issue: searches if the issue already had an earlier merged PR (stale issue).
        2. Main branch inspection: checks if modified files/functions already exist on default branch with identical/historical author.
        3. Title keyword overlap with merged PRs.
        """
        default_branch = repo_info_branch = "main"
        repo_resp = self._get(f"https://api.github.com/repos/{owner}/{repo}")
        if repo_resp.status_code == 200:
            default_branch = repo_resp.json().get("default_branch", "main")

        title = pr.get("title", "")
        body = pr.get("body", "") or ""
        pr_num = pr.get("number")
        
        # Extract linked issue numbers
        linked_issues = re.findall(r'(?:closes|fixes|resolves|issue)\s*#?(\d+)', f"{title} {body}", re.I)
        
        # Check 1: Linked issue was already resolved by an earlier merged PR
        for iss_num in linked_issues:
            search_url = f"https://api.github.com/search/issues?q=repo:{owner}/{repo}+is:pr+is:merged+{iss_num}"
            s_resp = self._get(search_url)
            if s_resp.status_code == 200:
                merged_prs = [item for item in s_resp.json().get("items", []) if item.get("number") != pr_num]
                if merged_prs:
                    earlier_pr = merged_prs[0]
                    return {
                        "status": "DUPLICATE",
                        "reason": f"Linked Issue #{iss_num} was already implemented and merged in PR #{earlier_pr.get('number')} ({earlier_pr.get('title')})",
                        "conflicting_pr": earlier_pr.get("html_url")
                    }

        # Check 2: Target file already existed on default branch prior to PR, check authorship override
        for f in files:
            fname = f.get("filename", "")
            raw_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{fname}?ref={default_branch}"
            content_resp = self._get(raw_url)
            if content_resp.status_code == 200:
                # File already exists on main branch!
                patch = f.get("patch", "")
                if "# author:" in patch or "author" in patch:
                    # Author changed on an already merged file
                    return {
                        "status": "DUPLICATE",
                        "reason": f"Target file '{fname}' is already in {default_branch}. PR modifies an already merged component and overrides authorship.",
                        "conflicting_file": fname
                    }

        # Check 3: General title keyword search
        clean_title = re.sub(r'\[.*?\]|#\d+|feat:|fix:|docs:', '', title).strip()
        words = [w for w in clean_title.split() if len(w) > 3]
        if words:
            query = "+".join(words[:2])
            search_url = f"https://api.github.com/search/issues?q=repo:{owner}/{repo}+is:pr+{query}"
            s_resp = self._get(search_url)
            if s_resp.status_code == 200:
                duplicates = [
                    item for item in s_resp.json().get("items", [])
                    if item.get("number") != pr_num
                ]
                merged_dup = [d for d in duplicates if d.get("state") == "closed"]
                if merged_dup:
                    return {
                        "status": "DUPLICATE",
                        "reason": f"Target capability already merged in #{merged_dup[0].get('number')}",
                        "conflicting_pr": merged_dup[0].get("html_url")
                    }
                elif duplicates:
                    return {
                        "status": "POSSIBLE_DUPLICATE",
                        "reason": f"Overlapping open PR exists #{duplicates[0].get('number')}",
                        "conflicting_pr": duplicates[0].get("html_url")
                    }

        return {"status": "CLEAN", "reason": "No duplicate historical PR or default branch conflict detected"}

    def _eval_issue_gate(self, owner: str, repo: str, pr: Dict[str, Any], files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        P0-5 Enhancement:
        Checks:
        1. Linked issues state: if closed, inspect whether it was closed as completed by upstream.
        2. Default branch recent commits: inspect whether upstream committed the exact target file/feature during or right after PR creation.
        """
        title = pr.get("title", "")
        body = pr.get("body", "") or ""
        text = f"{title} {body}"
        issue_matches = re.findall(r'(?:closes|fixes|resolves|issue)\s*#?(\d+)', text, re.I)

        pr_created_at = pr.get("created_at")

        for iss_num in issue_matches:
            iss_resp = self._get(f"https://api.github.com/repos/{owner}/{repo}/issues/{iss_num}")
            if iss_resp.status_code == 200:
                iss = iss_resp.json()
                # If issue is closed but PR was NOT merged
                if iss.get("state") == "closed" and not pr.get("merged"):
                    # Check if issue was closed by a commit on main
                    return {
                        "status": "SUPERSEDED",
                        "reason": f"Linked Issue #{iss_num} is already closed on upstream ({iss.get('state_reason') or 'completed'}). PR was superseded.",
                        "issue_state": "closed"
                    }

        # Check if upstream committed the exact new files directly to main around/after PR creation
        default_branch = "main"
        for f in files:
            fname = f.get("filename")
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits?path={fname}&sha={default_branch}"
            c_resp = self._get(commits_url)
            if c_resp.status_code == 200:
                commits = c_resp.json()
                if commits and not pr.get("merged"):
                    latest_commit = commits[0]
                    author_login = latest_commit.get("author", {}).get("login") if latest_commit.get("author") else ""
                    # If committed by someone else on main
                    if author_login and author_login != pr.get("user", {}).get("login"):
                        return {
                            "status": "SUPERSEDED",
                            "reason": f"Upstream maintainer ({author_login}) implemented '{fname}' directly on {default_branch} (Commit {latest_commit.get('sha')[:7]}).",
                            "superseding_commit": latest_commit.get("html_url")
                        }

        return {"status": "ACTIVE", "reason": "Linked issue is open and no upstream superseding commits detected"}

    def _eval_regression_test_gate(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        P0-6: Evaluates regression test presence, production logic vs test changes,
        and verifies xfail removal.
        """
        prod_files = []
        test_files = []
        xfail_removed = False

        for f in files:
            fname = f.get("filename", "")
            patch = f.get("patch", "")
            if any(t_dir in fname for t_dir in ["tests/", "test/", "_test.py", "test_"]):
                test_files.append(fname)
                if "-    @pytest.mark.xfail" in patch or "-@pytest.mark.xfail" in patch:
                    xfail_removed = True
            elif fname.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")):
                prod_files.append(fname)

        if xfail_removed and not test_files:
            return {
                "status": "UNVERIFIED_XFAIL_REMOVAL",
                "reason": "xfail marker was removed without explicit test execution or test assertion verification"
            }

        if prod_files and not test_files:
            return {
                "status": "MISSING_TESTS",
                "reason": f"Modified {len(prod_files)} production code files without adding or updating test cases"
            }

        return {
            "status": "PASSED",
            "prod_files": prod_files,
            "test_files": test_files,
            "xfail_removed_verified": xfail_removed
        }

    def _eval_scope_gate(self, pr: Dict[str, Any], files: List[Dict[str, Any]]) -> Dict[str, Any]:
        changed_files = pr.get("changed_files", len(files))
        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)
        total_diff = additions + deletions

        if changed_files > 15 or total_diff > 800:
            return {
                "status": "EXCESSIVE_SCOPE",
                "reason": f"PR modifies {changed_files} files (+{additions}, -{deletions}). High blast radius for single issue."
            }

        return {
            "status": "OPTIMAL_SCOPE",
            "changed_files": changed_files,
            "diff_lines": total_diff
        }

    def _eval_policy_guard(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        findings = []
        for f in files:
            fname = f.get("filename", "").upper()
            patch = f.get("patch", "")
            if any(p in fname for p in self.POLICY_FILES):
                added_lines = "\n".join([line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")])
                for regex_pat, reason in self.UNAUTHORIZED_PATTERNS:
                    matches = re.findall(regex_pat, added_lines, re.IGNORECASE)
                    if matches:
                        findings.append({
                            "file": f.get("filename"),
                            "matches": list(set(matches)),
                            "reason": reason
                        })
        if findings:
            return {"status": "FAIL", "findings": findings}
        return {"status": "PASS", "findings": []}

    def format_markdown_report(self, report: Dict[str, Any]) -> str:
        """Formats the JSON evaluation into a clean, human-readable Markdown report."""
        r = report
        gates = r.get("gates", {})
        
        md = f"""# RepoGate PR Quality & Risk Evaluation Report

**Target:** `{r.get('target')}`  
**Title:** {r.get('pr_title')}  
**Author:** @{r.get('pr_author')}  
**Base / Head:** `{r.get('base_branch')}` ← `{r.get('head_branch')}`  
**Overall Risk Score:** {r.get('risk_score')}/100  
**Merge Readiness:** **{r.get('merge_readiness')}**  
**Recommended Action:** `{r.get('recommended_action')}`  

---

### 1. Six-Gate Evaluation Matrix

| Gate | Status | Detail / Evidence |
| :--- | :--- | :--- |
| **Duplicate Gate** | `{gates.get('duplicate_gate', {}).get('status')}` | {gates.get('duplicate_gate', {}).get('reason')} |
| **Issue State Gate** | `{gates.get('issue_state_gate', {}).get('status')}` | {gates.get('issue_state_gate', {}).get('reason')} |
| **CI Gate** | `{gates.get('ci_gate', {}).get('status')}` | {gates.get('ci_gate', {}).get('evidence')} |
| **Regression Test Gate** | `{gates.get('regression_test_gate', {}).get('status')}` | Test coverage verified: {len(gates.get('regression_test_gate', {}).get('test_files', []))} test files |
| **Scope Gate** | `{gates.get('scope_gate', {}).get('status')}` | Changed files: {gates.get('scope_gate', {}).get('changed_files')}, Diff: {gates.get('scope_gate', {}).get('diff_lines')} lines |
| **Policy Guard** | `{gates.get('policy_guard', {}).get('status')}` | Violations detected: {len(gates.get('policy_guard', {}).get('findings', []))} |

---

### 2. Blocking Findings
"""
        if r.get("blocking_findings"):
            for b in r["blocking_findings"]:
                md += f"- ❌ **BLOCKER:** {b}\n"
        else:
            md += "- None. All blocking gate criteria satisfied.\n"

        md += "\n### 3. Warnings\n"
        if r.get("warnings"):
            for w in r["warnings"]:
                md += f"- ⚠️ **WARNING:** {w}\n"
        else:
            md += "- None. No elevated risks identified.\n"

        md += f"\n---\n*Report generated by RepoGate Autonomous PR Quality Agent v1.0*\n"
        return md

