"""A system's source is found in its `compressed/` archives, whatever they are named."""
import io
import os
import zipfile

from concentration_divergence_study import fontana


def _zip(files: dict) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return b.getvalue()


def _system(corpus, system, archives: dict):
    comp = os.path.join(corpus, "Systems", system.split("-")[0], system, "compressed")
    os.makedirs(comp)
    os.makedirs(os.path.join(os.path.dirname(comp), "src"))      # empty, as in the corpus
    for name, data in archives.items():
        with open(os.path.join(comp, name), "wb") as fh:
            fh.write(data)
    return comp


def test_the_archive_with_the_most_java_files_whatever_its_name(tmp_path):
    corpus = str(tmp_path)
    comp = _system(corpus, "argouml-0.34", {
        "ArgoUML-0.34-src.tar.gz.zip": _zip({"a/A.java": "", "a/B.java": ""}),
        "ArgoUML-0.34.zip": _zip({"argouml.jar": _zip({"a/A.class": ""})})})
    assert fontana.find_archive(corpus, "argouml-0.34") == [os.path.join(comp, "ArgoUML-0.34-src.tar.gz.zip")]


def test_a_source_jar_nested_in_an_archive(tmp_path):
    corpus = str(tmp_path)
    comp = _system(corpus, "weka-3.7.5", {
        "weka-3-7-5.zip": _zip({"weka-3-7-5/weka-src.jar": _zip({"weka/A.java": "", "weka/B.java": ""}),
                                "weka-3-7-5/x.java": ""})})
    members = fontana.find_archive(corpus, "weka-3.7.5")
    assert members == [os.path.join(comp, "weka-3-7-5.zip") + "!weka-3-7-5/weka-src.jar"]
    dest = str(tmp_path / "out")
    fontana.unpack(members, dest)
    assert sorted(os.listdir(os.path.join(dest, "weka"))) == ["A.java", "B.java"]


def test_a_top_level_archive_wins_a_tie_and_modules_are_taken_together(tmp_path):
    corpus = str(tmp_path)
    comp = _system(corpus, "squirrel_sql-3.1.2", {
        "src.jar": _zip({"p/A.java": ""}),
        "standard.zip": _zip({"plugins/graph/src.jar": _zip({"p/A.java": ""})})})
    assert fontana.find_archive(corpus, "squirrel_sql-3.1.2") == [os.path.join(comp, "src.jar")]
    corpus2 = str(tmp_path / "c2")
    comp2 = _system(corpus2, "jung-2.0.1", {
        "jung2-sources.zip": _zip({"jung-api-2.0.1-sources.jar": _zip({"a/A.java": ""}),
                                   "jung-io-2.0.1-sources.jar": _zip({"b/B.java": ""})})})
    members = fontana.find_archive(corpus2, "jung-2.0.1")
    outer = os.path.join(comp2, "jung2-sources.zip")
    assert members == [outer + "!jung-api-2.0.1-sources.jar", outer + "!jung-io-2.0.1-sources.jar"]
    corpus3 = str(tmp_path / "c3")
    comp3 = _system(corpus3, "jena-2.6.3", {
        "jena-2.6.3.zip": _zip({"Jena-2.6.3/jena-2.6.3-sources.jar": _zip({"a/A.java": "", "a/B.java": ""}),
                                "Jena-2.6.3/lib/iri-0.8-sources.jar": _zip({"b/B.java": ""})})})
    assert fontana.find_archive(corpus3, "jena-2.6.3") == [
        os.path.join(comp3, "jena-2.6.3.zip") + "!Jena-2.6.3/jena-2.6.3-sources.jar"]


def test_no_java_source_is_no_archive(tmp_path):
    corpus = str(tmp_path)
    _system(corpus, "x-1.0", {"x-1.0.zip": _zip({"x.class": ""})})
    assert fontana.find_archive(corpus, "x-1.0") is None
