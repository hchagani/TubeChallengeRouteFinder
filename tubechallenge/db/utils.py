from tubechallenge.db.graph import get_many as get_graphs

from sqlalchemy.orm import Session


def get_graph_ids(rec_infos: list[dict], session: Session) -> set[int]:
    """Extract graph IDs with which newly created records shall be associated.

    Args:
        rec_infos (list[dict]): data required to create database records. These
          dictionaries should contain the graph IDs.
        session (Session): database session.

    Returns:
        set of graph IDs.
    """
    graph_ids = [rec_info.get("graph_id") for rec_info  in rec_infos]
    db_graph_ids = {g.id for g in get_graphs(session, graph_ids=graph_ids)}

    return db_graph_ids
