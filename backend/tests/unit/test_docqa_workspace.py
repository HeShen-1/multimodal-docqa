from scripts.training.docqa_workspace import DOCQA_WORKSPACE_DIRS, ensure_docqa_workspace


def test_ensure_docqa_workspace_creates_expected_directories(tmp_path):
    workspace_root = tmp_path / "docqa_workspace"

    paths = ensure_docqa_workspace(workspace_root)

    assert set(paths) == set(DOCQA_WORKSPACE_DIRS)
    for key, path in paths.items():
        assert path.exists(), key
        assert path.is_dir(), key
        assert path.parent == workspace_root
