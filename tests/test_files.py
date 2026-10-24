"""A clone holding only files.CLONE_ONLY reads, to every file-level measure, as the full clone."""
import os
import subprocess

from complexity_concentration_study import extract as p1_extract
from complexity_concentration_study import study as p1
from open_source_repository_sampler.checkout import clone_at, sparse_patterns

from concentration_divergence_study import files


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@x",
                        "GIT_COMMITTER_NAME": "a", "GIT_COMMITTER_EMAIL": "a@x"})


def _repo(path):
    tree = {"src/main/java/a/A.java": "package a;\nclass A { void m() { if (true) {} } }\n",
            "src/main/java/a/B.JAVA": "package a;\nclass B {}\n",
            "web/app.ts": "function f(x) { return x ? 1 : 2; }\n",
            "tool/k.kt": "fun f() = 1\n", "pom.xml": "<project>org.springframework</project>",
            "sub/build.gradle": "implementation 'com.google.inject:guice'", "Dockerfile": "FROM x",
            "img/logo.png": "png", "lib/dep.jar": "jar", "README.md": "hi"}
    for rel, text in tree.items():
        os.makedirs(os.path.dirname(os.path.join(path, rel)) or path, exist_ok=True)
        with open(os.path.join(path, rel), "w") as fh:
            fh.write(text)
    _git(path, "init", "--quiet", "-b", "main")
    _git(path, "add", "-A")
    _git(path, "commit", "--quiet", "-m", "c")
    _git(path, "config", "uploadpack.allowFilter", "true")
    _git(path, "config", "uploadpack.allowAnySHA1InWant", "true")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True,
                          text=True).stdout.strip()


def test_clone_only_names_every_file_a_measure_reads():
    assert set(p1_extract.SOURCE_EXTS) <= set(files.CLONE_ONLY)
    assert set(files.BUILD_FILES) <= set(files.CLONE_ONLY)
    assert set(p1._APP_FILES) <= set(files.CLONE_ONLY)
    sparse_patterns(files.CLONE_ONLY)                    # the sampler accepts every entry


def test_a_filtered_clone_measures_as_the_full_one(tmp_path):
    remote = str(tmp_path / "remote")
    os.makedirs(remote)
    commit = _repo(remote)
    full, only = str(tmp_path / "full"), str(tmp_path / "only")
    assert clone_at("file://" + remote, commit, full) is None
    assert clone_at("file://" + remote, commit, only, only=files.CLONE_ONLY) is None
    assert not os.path.exists(os.path.join(only, "img", "logo.png"))
    assert p1_extract.scan_files(only) == p1_extract.scan_files(full)
    assert files.di_frameworks(only) == files.di_frameworks(full)
    assert p1.classify_kind(only, {}) == p1.classify_kind(full, {}) == "application"
