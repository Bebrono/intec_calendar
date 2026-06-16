from app.services.event_mapper import EventMapper


def test_sync_metadata_is_added_and_not_duplicated():
    mapper = EventMapper()

    description = mapper.with_sync_metadata(
        "Planning",
        sync_group_id="sync_001",
        original_source_system="outlook",
    )
    repeated = mapper.with_sync_metadata(
        description,
        sync_group_id="sync_001",
        original_source_system="outlook",
    )

    assert mapper.extract_sync_id(repeated) == "sync_001"
    assert mapper.extract_source(repeated) == "outlook"
    assert repeated.count("[SYNC_ID: sync_001]") == 1
    assert repeated.count("[SOURCE: outlook]") == 1
    assert mapper.strip_sync_metadata(repeated) == "Planning"
