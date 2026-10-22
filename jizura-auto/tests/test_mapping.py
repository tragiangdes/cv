"""Unit test for the word -> lyric-character mapping (no Whisper needed): python3 tests/test_mapping.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import jizura_auto as J

raw = '夜明けの色を/覚えてる\n*透明*なままじゃ終われない!\n[interlude 4]\nI remember/the dawn|note\n'
lines, _ = J.parse_lyrics(raw)
assert [L['sung'] for L in lines] == ['夜明けの色を覚えてる', '透明なままじゃ終われない', '', 'I remember the dawn'], lines
# aligner output with typical noise: leading spaces, different case, a dropped char, a mis-heard word
words = [(' 夜明け', 1.0, 1.6), ('の', 1.6, 1.8), ('色を', 1.8, 2.4), ('覚えてる', 2.6, 3.6),
         (' 透明', 5.0, 5.6), ('な', 5.6, 5.8), ('ままじゃ', 5.8, 6.6), ('終われ', 6.6, 7.2),          # 'ない' missing
         (' i', 12.0, 12.2), (' Remember', 12.2, 12.9), (' a', 13.0, 13.1), (' dawn', 13.1, 13.8)]  # 'the' -> 'a'
per = J.char_times(words, lines)
T = J.build_timing(lines, per, 0.1)
assert abs(T[0]['s'] - 0.9) < 1e-6 and abs(T[0]['c'][6] - 2.5) < 1e-6, T[0]     # 覚 starts at 2.6 - lead
assert T[2]['interlude'] and T[2]['s'] > T[1]['e'], T[2]
assert all(b >= a for t in T if t and t['c'] for a, b in zip(t['c'], t['c'][1:])), 'non-monotonic'
assert len(T[1]['c']) == len(J.chars_of('透明なままじゃ終われない')) and T[1]['c'][-1] >= 7.0, T[1]
assert abs(T[3]['c'][J.chars_of('I remember the dawn').index('d')] - 13.0) < 0.15, T[3]
print('mapping ok', [(t['s'], t.get('e')) for t in T])
