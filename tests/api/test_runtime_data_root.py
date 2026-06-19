from pathlib import Path

import pytest

from dillon_finances.runtime import (
    DataRootConfigurationError,
    REQUIRED_DATA_ROOT_DIRS,
    bootstrap_data_root,
)


def test_bootstrap_data_root_creates_required_directories(tmp_path):
    data_root = tmp_path / "Dillon_Finances_Data"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    bootstrap_data_root(data_root, repo_root=repo_root)

    for directory in REQUIRED_DATA_ROOT_DIRS:
        assert (data_root / directory).is_dir()


def test_bootstrap_data_root_rejects_directory_inside_git_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    data_root = repo_root / "local_data"

    with pytest.raises(DataRootConfigurationError, match="outside the git repository"):
        bootstrap_data_root(data_root, repo_root=repo_root)


def test_bootstrap_data_root_accepts_directory_next_to_git_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    data_root = tmp_path / "Dillon_Finances_Data"

    resolved = bootstrap_data_root(data_root, repo_root=repo_root)

    assert resolved == data_root.resolve()
    assert not Path(resolved).is_relative_to(repo_root.resolve())
