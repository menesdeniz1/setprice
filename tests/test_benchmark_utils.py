# -*- coding: utf-8 -*-
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.web_backend.database import Base
from src.web_backend import models, benchmark_utils


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    benchmark_utils.seed_benchmark_entries(session)
    yield session
    session.close()


def test_seed_is_idempotent(db):
    count_before = db.query(models.BenchmarkEntry).count()
    benchmark_utils.seed_benchmark_entries(db)
    count_after = db.query(models.BenchmarkEntry).count()
    assert count_before == count_after
    assert count_before > 0


def test_find_best_match_cpu(db):
    match = benchmark_utils.find_best_match(db, "Intel Core i5-14400F Box İşlemci", "İşlemci")
    assert match is not None
    name, score = match
    assert "i5-14400F" in name


def test_find_best_match_no_category(db):
    assert benchmark_utils.find_best_match(db, "Herhangi Bir Ürün", "Kulaklık") is None


def test_find_best_match_below_threshold(db):
    assert benchmark_utils.find_best_match(db, "Tamamen alakasız bir metin dizisi", "İşlemci") is None


def test_normalize_score_range(db):
    score = benchmark_utils.normalize_score(db, "İşlemci", 25600)  # i5-14400F seviyesi
    assert 0 <= score <= 100
