from trajectory_gym.env.database import connect, reset_from_dump


def test_world_sizes(db):
    assert db.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 60
    assert db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 25
    assert db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0] == 20
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 180
    assert db.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0


def test_reset_wipes_episode_mutations(db):
    db.execute(
        "INSERT INTO refunds (id, order_id, amount_cents, reason, created_at, created_by) "
        "VALUES ('R999999', 'O0001', 100, 'x', datetime('now'), 'agent')"
    )
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 1

    reset_from_dump(db)
    assert db.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 0


def test_reset_is_byte_identical():
    conn_a = connect(":memory:")
    reset_from_dump(conn_a)
    dump_a = list(conn_a.iterdump())

    conn_b = connect(":memory:")
    reset_from_dump(conn_b)
    dump_b = list(conn_b.iterdump())

    assert dump_a == dump_b
    conn_a.close()
    conn_b.close()


def test_reset_twice_on_same_connection_is_identical(db):
    dump_1 = list(db.iterdump())
    reset_from_dump(db)
    dump_2 = list(db.iterdump())
    assert dump_1 == dump_2
