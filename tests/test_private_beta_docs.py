"""The private-beta kit must stay honest about unsigned builds and privacy."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BETA = ROOT / "docs" / "private-beta"


def read(name):
    return (BETA / name).read_text(encoding="utf-8")


def test_kit_is_complete():
    for name in ("README.md", "checklist-windows.md", "procedure-environnement-propre.md",
                 "revue-licences-bloquantes.md", "notice-securite-version-non-signee.md",
                 "guide-testeur.md", "retours-et-bugs.md"):
        assert (BETA / name).is_file(), name


def test_notice_does_not_overstate_protection():
    text = read("notice-securite-version-non-signee.md")
    assert "n'a pas de signature" in text
    assert "issue #26" in text
    assert "Une signature, même future, ne change pas ce point" in text
    assert "autre canal" in text


def test_tester_guide_requires_hash_check_before_smartscreen():
    text = read("guide-testeur.md")
    assert text.index("Get-FileHash") < text.index("Informations complémentaires")
    assert "Seulement si l'empreinte" in text
    assert "publiques" in text  # public issue tracker warning


def test_feedback_keeps_personal_and_security_data_private():
    text = read("retours-et-bugs.md")
    assert "downloads.json" in text and "Ne jamais joindre" in text
    assert "SECURITY.md" in text
    bug = (ROOT / ".github" / "ISSUE_TEMPLATE" / "beta-privee-bug.yml").read_text(encoding="utf-8")
    assert "Cette issue est publique" in bug
    assert "required: true" in bug.split("id: privacy", 1)[1]
    assert "security/advisories/new" in (ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")
    assert (ROOT / "SECURITY.md").is_file()


def test_clean_environment_procedure_keeps_defences_enabled():
    text = read("procedure-environnement-propre.md")
    assert "ne rien désactiver" in text
    assert "expire après 14 jours" in text
    assert "SHA-256" in text


def test_workflow_publishes_hashes_in_summary_and_artifact():
    workflow = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    assert "dist/SHA256SUMS.txt" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "unsigned" in workflow.split("SHA-256 hashes of the distributable files", 1)[1][:1500]


def test_readme_gives_an_explicit_go_no_go_rule():
    text = read("README.md")
    assert "GO" in text and "NO-GO" in text
    assert "Ne pas" in text


def test_provenance_records_the_branch_head_commit():
    workflow = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    assert "id: source" in workflow
    assert 'echo "commit=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"' in workflow
    assert "head_commit = '${{ steps.source.outputs.commit }}'" in workflow
    assert "source ${{ steps.source.outputs.commit }}" in workflow


def test_automation_workflow_is_serialized_and_reports_without_publishing():
    workflow = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    assert '"automation/rapido-beta2-*"' in workflow
    assert 'cron: "17 */3 * * *"' in workflow
    assert "github.event.pull_request.head.ref" in workflow
    assert "cancel-in-progress: false" in workflow
    report = workflow.split("  automation-report:", 1)[1].split("\n  release:", 1)[0]
    assert "issues: write" in report
    assert 'TRACKING_ISSUE: "37"' in report
    assert "gh issue comment" in report
    assert 'echo "publishable=false"' in workflow
