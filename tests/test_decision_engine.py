# -*- coding: utf-8 -*-
import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from decision_engine import DecisionEngine

def test_bull_trap():
    engine = DecisionEngine()
    
    # Normal trend
    assert engine.detect_bull_trap(15000, [15000, 15000, 15000]) == False
    
    # Gerçek dip (Sürekli düşüş)
    assert engine.detect_bull_trap(12000, [15000, 14000, 13000]) == False
    
    # Sahte İndirim (Önce 20k, sonra 15k, ama medyan 10k)
    # Median of [10000, 10000, 10000, 20000] is 10000
    assert engine.detect_bull_trap(15000, [10000, 10000, 10000, 20000, 15000]) == True

def test_value_score():
    engine = DecisionEngine()
    
    # Aynı fiyat
    assert engine.calculate_value_score(100, 100) == 50.0
    
    # Ucuz (iyi value)
    assert engine.calculate_value_score(80, 100) == 70.0
    
    # Pahalı (kötü value)
    assert engine.calculate_value_score(120, 100) == 30.0
