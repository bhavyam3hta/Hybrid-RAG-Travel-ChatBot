"""Credential-free keyword demonstration; not semantic retrieval or an LLM."""
import json
import re
from pathlib import Path

NODES = json.loads((Path(__file__).parent / 'vietnam_travel_dataset.json').read_text())
BY_ID = {node['id']: node for node in NODES}
STOP = set('i a an the and or in at to for of with me my want visit places place vietnam recommend some where can go is are do what best'.split())

def tokens(text):
    return {word.rstrip('s') for word in re.findall(r'\w+', text.lower()) if word not in STOP and len(word) > 1}

def answer_query(query, top_k=5):
    wanted = tokens(query)
    ranked = []
    for node in NODES:
        searchable = ' '.join(str(node.get(k, '')) for k in ('name', 'city', 'region', 'description', 'semantic_text', 'tags'))
        overlap = wanted & tokens(searchable)
        if overlap:
            score = round(100 * len(overlap) / len(wanted), 1)
            ranked.append((score, node))
    ranked.sort(key=lambda item: item[0], reverse=True)
    matches, facts, paragraphs = [], [], []
    for score, node in ranked[:top_k]:
        matches.append(dict(id=node['id'], name=node['name'], city=node.get('city', node.get('region', 'Vietnam')), type=node.get('type', 'Location'), tags=node.get('tags', []), score=score))
        paragraphs.append(node['name'] + '\n' + node.get('description', '') + '\nBest time in dataset: ' + node.get('best_time_to_visit', 'Not specified'))
        for connection in node.get('connections', [])[:6]:
            target = BY_ID.get(connection.get('target'))
            if target:
                facts.append(dict(source=node['id'], rel=connection.get('relation', 'RELATED_TO'), target_id=target['id'], target_name=target['name'], target_type=target.get('type', 'Location'), target_desc=target.get('description', '')[:250]))
    answer = 'LOCAL DEMO — keyword matches from the included dataset. No AI response was generated.\n\n'
    answer += '\n\n'.join(paragraphs) if matches else 'No keyword matches found. Try “beach”, “Hanoi”, “food”, or “trekking”.'
    return dict(query=query, answer=answer, matches=matches, graph_facts=facts[:15], mode='demo')
