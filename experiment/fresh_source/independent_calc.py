import math,re,itertools
def scalar(v):
    while isinstance(v, list) and len(v) == 1:
        v = v[0]
    return float(v)

def parse_params(params):
    factors = {}
    for key, val in params.items():
        m = re.fullmatch('p\\(([^|)]+)(?:\\|([^)]+))?\\)', key)
        if not m:
            raise ValueError('unsupported parameter key ' + key)
        var = m.group(1).strip()
        parents = [x.strip() for x in (m.group(2) or '').split(',') if x.strip()]
        factors[var] = (parents, val)
    return factors

def probability_one(factor, assignment):
    parents, val = factor
    for pa in parents:
        val = val[assignment[pa]]
    return scalar(val)

def joint(factors, intervention=None):
    intervention = intervention or {}
    variables = list(factors)
    rows = []
    for bits in itertools.product([0, 1], repeat=len(variables)):
        a = dict(zip(variables, bits))
        prob = 1.0
        for v in variables:
            if v in intervention:
                prob *= float(a[v] == intervention[v])
            else:
                p = probability_one(factors[v], a)
                prob *= p if a[v] else 1 - p
        if prob > 1e-15:
            rows.append((a, prob))
    if abs(sum((p for _, p in rows)) - 1) > 1e-08:
        raise ValueError('joint distribution not normalized')
    return rows

def from_given(meta, rounded=False):
    g = meta['given_info']

    def tr(x):
        return [tr(v) for v in x] if isinstance(x, list) else round(x, 2)
    if rounded:
        g = {k: tr(v) for k, v in g.items()}
    typ = meta['query_type']
    graph = meta['graph_id']
    if graph == 'frontdoor' and typ in {'ate', 'ett', 'nie'}:
        m = g['p(V3 | X)']
        y = g['p(Y | X, V3)']
        if typ == 'ett':
            return ((m[1] - m[0]) * (y[1][1] - y[1][0]), '(m1-m0)*(y11-y10)')
        x = scalar(g['p(X)'])
        return ((m[1] - m[0]) * ((1 - x) * (y[0][1] - y[0][0]) + x * (y[1][1] - y[1][0])), '(m1-m0)*[(1-pX)*(y01-y00)+pX*(y11-y10)]')
    if graph == 'mediation' and typ in {'nie', 'nde'}:
        m = g['p(V2 | X)']
        y = g['p(Y | X, V2)']
        if typ == 'nie':
            return ((m[1] - m[0]) * (y[0][1] - y[0][0]), '(m1-m0)*(y01-y00)')
        return ((1 - m[0]) * (y[1][0] - y[0][0]) + m[0] * (y[1][1] - y[0][1]), '(1-m0)*(y10-y00)+m0*(y11-y01)')
    if graph == 'arrowhead' and typ == 'nie':
        y = g['p(Y | X, V3)']
        m = g['p(V3 | X, V2)']
        z = scalar(g['p(V2)'])
        return ((y[0][1] - y[0][0]) * ((1 - z) * (m[1][0] - m[0][0]) + z * (m[1][1] - m[0][1])), '(y01-y00)*[(1-pZ)*(m10-m00)+pZ*(m11-m01)]; evaluates supplied estimand, not proof that it identifies natural indirect effect')
    if graph == 'diamondcut' and typ == 'ate':
        y = g['p(Y | V1, X)']
        z = scalar(g['p(V1)'])
        return ((1 - z) * (y[0][1] - y[0][0]) + z * (y[1][1] - y[1][0]), '(1-pZ)*(y01-y00)+pZ*(y11-y10)')
    raise ValueError('unsupported type/graph')

def from_scm(model, meta):
    typ = meta['query_type']
    graph = meta['graph_id']
    p = model['params']
    f = parse_params(p)
    if typ == 'ate' or (typ == 'nie' and graph == 'frontdoor'):
        return (sum((a['Y'] * q for a, q in joint(f, {'X': 1}))) - sum((a['Y'] * q for a, q in joint(f, {'X': 0}))), 'Truncated factorization do(X=1)-do(X=0); frontdoor has no direct X->Y edge, so NIE equals ATE.')
    if typ == 'ett' and graph == 'frontdoor':
        obs = joint(f)
        px = sum((q for a, q in obs if a['X'] == 1))
        pu = [sum((q for a, q in obs if a['X'] == 1 and a['V1'] == u)) / px for u in [0, 1]]
        y = p['p(Y | V1, V3)']
        m = p['p(V3 | X)']
        return (sum((pu[u] * (y[u][1] - y[u][0]) * (m[1] - m[0]) for u in [0, 1])), 'Sum_u P(u|X=1)*(m1-m0)*(y_u1-y_u0) from complete frontdoor CPTs.')
    if graph == 'mediation' and typ in {'nie', 'nde'}:
        return from_given({'given_info': p, 'graph_id': graph, 'query_type': typ})
    if typ == 'nie' and graph == 'arrowhead':
        z = scalar(p['p(V2)'])
        m = p['p(V3 | X, V2)']
        y = p['p(Y | X, V2, V3)']
        return (sum(([1 - z, z][k] * (m[1][k] - m[0][k]) * (y[0][k][1] - y[0][k][0]) for k in [0, 1])), 'Pure NIE under modular independent-noise binary SCM: sum_z P(z)*(m1z-m0z)*(y0z1-y0z0). Additional cross-world assumption is explicit.')
    raise ValueError('SCM scope unsupported')

def answer_for_effect(value, meta):
    if meta['query_type'] == 'det-counterfactual':
        return 'yes' if value else 'no'
    if abs(value) < 1e-10:
        return 'UNKNOWN_ZERO_EFFECT'
    positive_requested = bool(meta['polarity'])
    if meta['query_type'] == 'ett':
        if meta.get('treated') is not True or meta.get('result') is not True:
            raise ValueError('ETT language variant unsupported')
        positive_requested = not positive_requested
    return 'yes' if (value > 0) == positive_requested else 'no'
