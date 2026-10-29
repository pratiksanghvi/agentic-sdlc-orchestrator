from orchestrator.stages.codebase.graph import MAX_FILES, detect_stack, snapshot
from orchestrator.stages.design.rules import validate_stack


def test_detect_stack(tmp_path):
    assert detect_stack(tmp_path) is None
    (tmp_path / "pom.xml").write_text("<project/>")
    assert detect_stack(tmp_path) == "java21-springboot3-maven"


def test_snapshot_skips_build_output_and_enforces_budget(tmp_path):
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "A.java").write_text("x")
    (tmp_path / "B.java").write_text("class B {}")
    files, skipped = snapshot(tmp_path)
    assert list(files) == ["B.java"] and skipped == []
    for i in range(MAX_FILES + 1):
        (tmp_path / f"F{i}.java").write_text("x")
    _, skipped = snapshot(tmp_path)
    assert skipped


def test_brownfield_must_keep_existing_stack(config):
    class D:
        recommended_stack_id = "go122-chi"

    spec = {"non_functional_requirements": []}
    assert "keep that stack" in validate_stack(D(), config, spec,
                                               existing="java21-springboot3-maven")[0]
    assert validate_stack(D(), config, spec) == []
