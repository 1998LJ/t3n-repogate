import os
import json
from repogate_engine import RepoGateEngine

def main():
    engine = RepoGateEngine()
    
    cases = [
        ("yunaremaia", "driftcheck", 66, "high_quality_clean"),
        ("abduznik", "bitbox", 482, "duplicate_dirty_pr"),
        ("yunaremaia", "driftcheck", 68, "superseded_race_pr"),
    ]

    os.makedirs("demo_reports", exist_ok=True)

    for owner, repo, pr_num, label in cases:
        print(f"[*] Running RepoGate evaluation on {owner}/{repo} PR #{pr_num} ({label})...")
        report = engine.analyze_pr(owner, repo, pr_num)
        
        json_path = f"demo_reports/{label}_pr{pr_num}.json"
        md_path = f"demo_reports/{label}_pr{pr_num}.md"
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            
        md_content = engine.format_markdown_report(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        print(f"    -> Risk: {report['summary']['overall_risk_score']}/100 | Rec: {report['summary']['recommended_action']}")

    print("\n[+] All 3 Demo Cases evaluated and reports generated in demo_reports/")

if __name__ == "__main__":
    main()
