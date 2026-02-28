from __future__ import annotations

from polisyos.academic.openalex.topic_catalog import discover_topic_files, load_topics


def test_load_topics_skips_summary_and_index(tmp_path) -> None:
    topics_dir = tmp_path / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)

    (topics_dir / "relevant_topics_thematic_summary.csv").write_text("x,y\n", encoding="utf-8")
    (topics_dir / "relevant_topics_domain_files_index.csv").write_text("x,y\n", encoding="utf-8")
    (topics_dir / "relevant_topics_domain_test.csv").write_text(
        "id,display_name,description,works_count,cited_by_count,policy_block,policy_subblock,score_core,score_domain,score_context\n"
        "https://openalex.org/T1,Test Topic,desc,100,500,block,sub,1,2,3\n",
        encoding="utf-8",
    )

    files = discover_topic_files(topics_dir)
    assert len(files) == 1
    assert files[0].name == "relevant_topics_domain_test.csv"

    topics = load_topics(topics_dir)
    assert len(topics) == 1
    assert topics[0].topic_id == "T1"
    assert topics[0].display_name == "Test Topic"
