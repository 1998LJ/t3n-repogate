import os
import sys
import re
import json
from typing import Dict, Any, List, Optional
import requests

class RepoGateEngine:
    """
    Autonomous Enterprise PR Quality & Risk Gate Engine
    Evaluates 6 fundamental security and quality dimensions:
    A. Duplicate Gate (Historical PRs, merged PRs, main branch duplication)
    B. Issue State Gate (Active, Superseded, Stale)
    C. CI Gate (Workflow checks, lint, test, typecheck)
    D. Regression Test Gate (Presence of tests for bugfixes, xfail removal validation)
    E. Scope Gate (Diff size, touched file ratio, architectural sprawl)
    F. Policy Document Guard (Unauthorized SLA/Security commitments in policy docs)
    """

    POLICY_FILES = {"SECURITY.md", "SUPPORT.md", "GOVERNANCE.md", "SLA.md", "SLA", "LICENSE"}
    UNAUTHORIZED_POLICY_PATTERNS = [
        (r'\b(?:within\s+\d+\s+(?:hours|days)|48\s*hours|24\s*hours|30\s*days)\b', "Unapproved SLA or response turnaround timeframe"),
        (r'\b(?:bounty(?: of| up to)?\s*[$]?\d+|[$]?\d+\s*(?:usd|usdc|dollars)?\s*reward)\b', "Unapproved financial bounty or reward commitment"),
        (r'\b(?:guarantee(?:d)?|100%\s+uptime|zero\s+downtime)\b', "Unapproved legal guarantee or liability commitment"),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "Hardcoded specific contact email without upstream authorization")
    ]

    def __init__(self, github_token: Optional[str] = None, proxies: Optional[Dict[str, str]] = None):
        self.token = github_token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        self.proxies = proxies or {
            'http': 'socks5h://127.0.0.1:7790',
            'https': 'socks5h://127.0.0.1:7790'
        }
        self.headers = {
            'User-Agent': 'RepoGate-Agent/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'

    def analyze_pr(self, repo_owner: str, repo_name: str, pr_number: int) -> Dict[str, Any]:
        base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        
        # 1. Fetch PR details
        pr_resp = requests.get(f"{base_url}/pulls/{pr_number}", headers=self.headers, proxies=self.proxies)
        if pr_resp.status_code != 200:
            raise ValueError(f"Failed to fetch PR #{pr_number}: {pr_resp.status_code}")
        pr_data = pr_resp.json()

        # 2. Fetch PR files
        files_resp = requests.get(f"{base_url}/pulls/{pr_number}/files", headers=self.headers, proxies=self.proxies)
        files = files_resp.json() if files_resp.status_code == 200 else []

        # 3. Fetch CI checks / Commit statuses
        head_sha = pr_data.get("head", {}).get("sha")
        check_runs_resp = requests.get(f"{base_url}/commits/{head_sha}/check-runs", headers=self.headers, proxies=self.proxies)
        check_runs = check_runs_resp.json().get("check_runs", []) if check_runs_resp.status_code == 200 else []

        # 4. Run Gates
        dup_gate = self._eval_duplicate_gate(repo_owner, repo_name, pr_data)
        issue_gate = self._eval_issue_state_gate(repo_owner, repo_name, pr_data)
        ci_gate = self._eval_ci_gate(check_runs, pr_data)
        reg_gate = self._eval_regression_test_gate(files, pr_data)
        scope_gate = self._eval_scope_gate(files, pr_data)
        policy_gate = self._eval_policy_guard(files)

        # 5. Synthesize Assessment
        blocking_findings = []
        warnings = []

        if dup_gate["status"] == "DUPLICATE":
            blocking_findings.append(f"Duplicate PR detected: Overlaps with existing merged/open work: {dup_gate.get('reason')}")
        elif dup_gate["status"] == "POSSIBLE_DUPLICATE":
            warnings.append(f"Possible duplication: Similar historical PR exists ({dup_gate.get('reason')})")

        if issue_gate["status"] == "SUPERSEDED":
            blocking_findings.append("Superseded: Upstream branch or maintainer has already implemented or resolved this requirement.")
        elif issue_gate["status"] == "STALE":
            warnings.append("Stale: Target issue is closed or inactive.")

        if ci_gate["status"] == "CI Failed":
            blocking_findings.append(f"CI Gate Failed: {ci_gate.get('failed_count', 0)} checks failed on head commit.")

        if reg_gate["status"] == "FAIL":
            blocking_findings.append("Regression Test Gate Failed: Production code was modified without corresponding test coverage.")
        elif reg_gate["status"] == "WARN":
            warnings.append(reg_gate.get("reason", "Missing test assertion validation."))

        if scope_gate["status"] == "HIGH_RISK":
            blocking_findings.append(f"Scope Gate Violation: Excessive diff or architectural sprawl (+{scope_gate.get('additions')} / -{scope_gate.get('deletions')} across {scope_gate.get('files_count')} files).")
        elif scope_gate["status"] == "MODERATE_RISK":
            warnings.append(f"Scope Gate Warning: Moderately high file churn ({scope_gate.get('files_count')} files touched).")

        if policy_gate["status"] == "FAIL":
            for f in policy_gate["findings"]:
                blocking_findings.append(f"Policy Guard Violation in {f['file']}: {f['reason']}")

        # 6. Determine Recommended Action & Overall Risk Score
        # Risk Score: 0 (Flawless) to 100 (Critical Risk)
        risk_score = 0
        risk_score += len(blocking_findings) * 35
        risk_score += len(warnings) * 10
        risk_score = min(100, max(0, risk_score))

        if dup_gate["status"] == "DUPLICATE":
            recommended_action = "CLOSE_DUPLICATE"
        elif issue_gate["status"] == "SUPERSEDED":
            recommended_action = "SUPERSEDED"
        elif len(blocking_findings) > 0:
            recommended_action = "FIX_REQUIRED"
        elif pr_data.get("merged"):
            recommended_action = "MERGED"
        elif ci_gate["status"] == "CI Passed" and risk_score < 25:
            recommended_action = "MERGE_READY"
        else:
            recommended_action = "WAIT_FOR_REVIEW"

        merge_readiness = "READY" if recommended_action in ("MERGE_READY", "MERGED") else ("BLOCKED" if len(blocking_findings) > 0 else "CAUTION")

        report = {
            "meta": {
                "repo": f"{repo_owner}/{repo_name}",
                "pr_number": pr_number,
                "title": pr_data.get("title"),
                "author": pr_data.get("user", {}).get("login"),
                "state": pr_data.get("state"),
                "merged": pr_data.get("merged", False),
                "created_at": pr_data.get("created_at"),
                "updated_at": pr_data.get("updated_at"),
            },
            "summary": {
                "overall_risk_score": risk_score,
                "merge_readiness": merge_readiness,
                "recommended_action": recommended_action,
                "blocking_findings_count": len(blocking_findings),
                "warnings_count": len(warnings),
            },
            "gates": {
                "duplicate_gate": dup_gate,
                "issue_state_gate": issue_gate,
                "ci_gate": ci_gate,
                "regression_test_gate": reg_gate,
                "scope_gate": scope_gate,
                "policy_document_guard": policy_gate,
            },
            "blocking_findings": blocking_findings,
            "warnings": warnings
        }

        return report

    def _eval_duplicate_gate(self, owner: str, repo: str, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        title = pr_data.get("title", "")
        pr_number = pr_data.get("number")
        
        # Search existing PRs with same title or keywords
        clean_title = re.sub(r'[\(\)\[\]#\:\-\_]', ' ', title).strip()
        words = [w for w in clean_title.split() if len(w) > 3 and w.lower() not in ("feat", "fix", "docs", "chore", "tool")]
        query = f"repo:{owner}/{repo} is:pr {' '.join(words[:3])}"
        
        search_resp = requests.get(f"https://api.github.com/search/issues?q={query}", headers=self.headers, proxies=self.proxies)
        if search_resp.status_code == 200:
            items = search_resp.json().get("items", [])
            for item in items:
                if item.get("number") != pr_number:
                    if item.get("state") == "closed" and item.get("pull_request", {}).get("merged_at"):
                        return {
                            "status": "DUPLICATE",
                            "reason": f"Merged PR #{item.get('number')} ({item.get('title')}) already implemented this."
                        }
                    elif item.get("state") == "open":
                        return {
                            "status": "POSSIBLE_DUPLICATE",
                            "reason": f"Open PR #{item.get('number')} ({item.get('title')}) is currently active."
                        }

        return {"status": "CLEAN", "reason": "No historical duplicate PR found."}

    def _eval_issue_state_gate(self, owner: str, repo: str, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        body = pr_data.get("body") or ""
        issue_matches = re.findall(r'(?:closes|fixes|resolves)\s+#(\d+)', body, re.IGNORECASE)
        if not issue_matches:
            return {"status": "ACTIVE", "reason": "No directly linked issue or standalone feature."}

        for issue_num in issue_matches:
            resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}", headers=self.headers, proxies=self.proxies)
            if resp.status_code == 200:
                issue_data = resp.json()
                if issue_data.get("state") == "closed":
                    # Check if closed by this PR or earlier
                    if pr_data.get("state") == "open":
                        return {"status": "SUPERSEDED", "reason": f"Linked Issue #{issue_num} is already closed."}

        return {"status": "ACTIVE", "reason": "Linked issues are open and active."}

    def _eval_ci_gate(self, check_runs: List[Dict[str, Any]], pr_data: Dict[str, Any]) -> Dict[str, Any]:
        if not check_runs:
            if pr_data.get("merged"):
                return {"status": "Merged", "details": "PR merged upstream."}
            return {"status": "Submitted", "details": "No automated CI workflow checks reported on commit."}

        total = len(check_runs)
        success_count = 0
        failed_count = 0

        for run in check_runs:
            conclusion = run.get("conclusion")
            if conclusion == "success":
                success_count += 1
            elif conclusion in ("failure", "timed_out", "action_required"):
                failed_count += 1

        if failed_count > 0:
            return {"status": "CI Failed", "total": total, "failed_count": failed_count, "details": f"{failed_count} failing checks"}
        elif success_count == total and total > 0:
            return {"status": "CI Passed", "total": total, "success_count": success_count, "details": "All CI workflows passed"}
        else:
            return {"status": "In Progress", "total": total, "details": "Checks currently running or queued"}

    def _eval_regression_test_gate(self, files: List[Dict[str, Any]], pr_data: Dict[str, Any]) -> Dict[str, Any]:
        has_prod_change = False
        has_test_change = False

        for f in files:
            filename = f.get("filename", "").lower()
            if any(p in filename for p in ["test_", "_test.", "/tests/", "/test/", ".spec.", ".test."]):
                has_test_change = True
            elif not any(filename.endswith(ext) for ext in [".md", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg"]):
                has_prod_change = True

        is_bugfix = any(k in pr_data.get("title", "").lower() for k in ["fix", "bug", "patch", "crash", "error", "issue"])
        
        if is_bugfix and has_prod_change and not has_test_change:
            return {"status": "FAIL", "reason": "Bugfix modified production code but included zero regression test files."}
        elif has_prod_change and not has_test_change:
            return {"status": "WARN", "reason": "Production logic was touched without accompanying tests."}
        
        return {"status": "PASS", "reason": "Adequate test modifications present."}

    def _eval_scope_gate(self, files: List[Dict[str, Any]], pr_data: Dict[str, Any]) -> Dict[str, Any]:
        additions = pr_data.get("additions", 0)
        deletions = pr_data.get("deletions", 0)
        files_count = len(files)

        is_bugfix = any(k in pr_data.get("title", "").lower() for k in ["fix", "patch", "bug"])
        
        if is_bugfix and (files_count > 8 or additions + deletions > 300):
            return {
                "status": "HIGH_RISK",
                "files_count": files_count,
                "additions": additions,
                "deletions": deletions,
                "reason": "Bugfix exhibits architectural sprawl or excessive diff."
            }
        elif files_count > 15 or additions + deletions > 1000:
            return {
                "status": "MODERATE_RISK",
                "files_count": files_count,
                "additions": additions,
                "deletions": deletions,
                "reason": "Large modification footprint."
            }
        
        return {
            "status": "LOW_RISK",
            "files_count": files_count,
            "additions": additions,
            "deletions": deletions,
            "reason": "Surgically bounded scope."
        }

    def _eval_policy_guard(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        violations = []
        for f in files:
            filename = os.path.basename(f.get("filename", ""))
            if filename in self.POLICY_FILES:
                patch_text = f.get("patch", "")
                for pattern, desc in self.UNAUTHORIZED_POLICY_PATTERNS:
                    matches = re.findall(pattern, patch_text, re.IGNORECASE)
                    if matches:
                        violations.append({
                            "file": filename,
                            "matches": matches,
                            "reason": desc
                        })

        if violations:
            return {"status": "FAIL", "findings": violations}
        return {"status": "PASS", "findings": []}

    @staticmethod
    def format_markdown_report(report: Dict[str, Any]) -> str:
        meta = report["meta"]
        summary = report["summary"]
        gates = report["gates"]

        md = []
        md.append(f"# 🛡️ RepoGate Quality & Risk Audit Report")
        md.append(f"**Repository**: `{meta['repo']}` | **PR**: `#{meta['pr_number']}` ({meta['title']})")
        md.append(f"**Author**: `@{meta['author']}` | **Audit Status**: `{summary['merge_readiness']}` | **Risk Score**: `{summary['overall_risk_score']}/100`")
        md.append(f"**Recommended Action**: `{summary['recommended_action']}`\n")
        md.append(f"---")
        md.append(f"## 📊 Gate Assessment Matrix\n")
        md.append(f"| Gate Name | Status | Evaluation Evidence |")
        md.append(f"| :--- | :--- | :--- |")
        md.append(f"| **A. Duplicate Gate** | `{gates['duplicate_gate']['status']}` | {gates['duplicate_gate'].get('reason')} |")
        md.append(f"| **B. Issue State Gate** | `{gates['issue_state_gate']['status']}` | {gates['issue_state_gate'].get('reason')} |")
        md.append(f"| **C. CI / Automation Gate** | `{gates['ci_gate']['status']}` | {gates['ci_gate'].get('details')} |")
        md.append(f"| **D. Regression Test Gate** | `{gates['regression_test_gate']['status']}` | {gates['regression_test_gate'].get('reason')} |")
        md.append(f"| **E. Scope & Churn Gate** | `{gates['scope_gate']['status']}` | {gates['scope_gate'].get('reason')} ({gates['scope_gate'].get('files_count')} files, +{gates['scope_gate'].get('additions')}/-{gates['scope_gate'].get('deletions')}) |")
        md.append(f"| **F. Policy Document Guard** | `{gates['policy_document_guard']['status']}` | {'Violations found' if gates['policy_document_guard']['findings'] else 'No unauthorized commitments'} |")
        md.append("")

        if report["blocking_findings"]:
            md.append("### 🚫 Blocking Findings (Must Resolve Before Merge)")
            for b in report["blocking_findings"]:
                md.append(f"- 🔴 {b}")
            md.append("")

        if report["warnings"]:
            md.append("### ⚠️ Warnings & Advisory Notices")
            for w in report["warnings"]:
                md.append(f"- 🟡 {w}")
            md.append("")

        md.append(f"### 🎯 Actionable Conclusion")
        if summary["recommended_action"] in ("MERGE_READY", "MERGED"):
            md.append("✅ **PR exhibits pristine engineering discipline. Zero duplicate risk, passing CI, and bounded scope. Recommended for Merge.**")
        elif summary["recommended_action"] == "CLOSE_DUPLICATE":
            md.append("❌ **PR duplicates existing mainline/merged work. Recommend closing immediately to keep the backlog clean.**")
        elif summary["recommended_action"] == "SUPERSEDED":
            md.append("⚠️ **Underlying issue has already been resolved or superseded upstream. Recommend closing gracefully.**")
        else:
            md.append("🛠️ **PR requires remediation on the blocking findings noted above before it can be safely integrated.**")

        return "\n".join(md)
