from harness.memory.memory import Memory, RecallQuery
from harness.models import MemoryEntry


def test_store_and_recall_by_tag(tmp_path):
    mem = Memory(str(tmp_path / "mem.jsonl"))
    mem.store(MemoryEntry(id="1", tags=["convention", "test"], content="uses pytest", created_at="t0"))
    mem.store(MemoryEntry(id="2", tags=["lesson", "test"], content="don't edit conftest", created_at="t1"))
    got = mem.recall(RecallQuery(tags={"test"}))
    ids = {e.id for e in got}
    assert ids == {"1", "2"}


def test_recall_filters_by_multiple_tags_intersection(tmp_path):
    mem = Memory(str(tmp_path / "mem.jsonl"))
    mem.store(MemoryEntry(id="1", tags=["convention", "test"], content="a", created_at="t0"))
    mem.store(MemoryEntry(id="2", tags=["lesson", "test"], content="b", created_at="t1"))
    got = mem.recall(RecallQuery(tags={"lesson"}))
    assert {e.id for e in got} == {"2"}


def test_recall_empty_when_no_match(tmp_path):
    mem = Memory(str(tmp_path / "mem.jsonl"))
    mem.store(MemoryEntry(id="1", tags=["x"], content="a", created_at="t0"))
    assert mem.recall(RecallQuery(tags={"y"})) == []


def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "mem.jsonl")
    Memory(path).store(MemoryEntry(id="1", tags=["x"], content="a", created_at="t0"))
    got = Memory(path).recall(RecallQuery(tags={"x"}))
    assert {e.id for e in got} == {"1"}