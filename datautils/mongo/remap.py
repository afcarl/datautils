#!/usr/bin/env python
"""
Take a list of mongo documents and remap them
from:
    list of dicts
to:
    dict of lists/values

remapping can contain:
    queries: q
        can be global or local
            global : removes document in source [default]
            local : removes document in destination [not implemented]
    functions: f
        can be many-to-one or many-to-many


simple mapping
    'mongo.key' -> 'dict.key'

transform mapping
    func('mongo.key') -> 'dict.key'

compound mapping [assumes many-to-many]
    query(func('mongo.key')) -> 'dict.key'


Examples
------

remap(docs, {'dest': 'mongo.key'})
# [{'mongo.key': 1}, {'mongo.key': 2}] -> {'dest': [1, 2]}

remap(docs, {'dest': {'k': 'mongo.key', 'f': numpy.mean}})
# [{'mongo.key': 1}, {'mongo.key': 2}] -> {'dest': 1.5}

remap(docs, {'dest': {'k': 'mongo.key', 'q': {'$lt': 1}}})
# [{'mongo.key': 1}, {'mongo.key': 2}] -> {'dest': [2, ]}

# not supported...
remap(docs, {'dest':
    {'k': 'mongo.key', 'q': {'$gt': 2}, 'f': lambda x: x * 2}})
# [{'mongo.key': 1}, {'mongo.key': 2}] -> {'dest': [4, ]}
"""

from .. import ddict
from .. import qfilter


class MappingError(Exception):
    pass


def parse_mapping(mapping):
    """
    Split the mapping into:
        simple mappings
        queries
        functions
        function/queries

    None of this works because it doesn't take into account that there might
    be multiple mappings for a single mongokey
    """
    # dicts of key = destination key, value = query/mongo.key/function...
    ss, qs, fs, fqs = {}, {}, {}, {}
    for k, v in mapping.iteritems():
        if isinstance(v, (str, unicode)):
            ss[k] = v
            continue

        if not isinstance(v, dict):
            raise MappingError("%s must be a dict [key=%s]" % (v, k))
        if 'k' not in v:
            raise MappingError(
                "Mapping value missing key[k] [key=%s, value=%s]" % (k, v))

        if 'f' in v:
            # function
            if 'q' in v:
                raise NotImplementedError("Not yet supported")
                fqs[k] = v
            else:
                fs[k] = v
            continue

        if 'q' in v:
            # query
            # if a query for this key already exists, add to it
            qv = qs.get(v['k'], {})
            qv.update(v['q'])
            qs[v['k']] = qv
            # also add a simple mapping, so filtered items will be saved
            ss[k] = v['k']
            continue

        raise MappingError("Unknown mapping [key=%s, value=%s]" % (k, v))
    return ss, qs, fs, fqs


def apply_functions(docs, fs, rs=None):
    if rs is None:
        rs = [{} for _ in xrange(len(docs))]
    for (rk, v) in fs.iteritems():
        mk = v['k']
        frs = v['f']([d[mk] for d in docs])
        if hasattr(frs, '__len__') and (not isinstance(frs, (str, unicode))):
            # if a sequence was returned
            if len(frs) != len(rs):
                raise MappingError(
                    "Function(%s) result incorrect length [%s != %s]"
                    % (v['k'], len(frs), len(rs)))
            for i in xrange(len(frs)):
                rs[i][rk] = frs[i]
        else:
            # if a single value was returned
            for i in xrange(len(rs)):
                rs[i][rk] = frs
    return rs


def remap(cursor, mapping, asdocs=True):
    docs = [ddict.DDict(d) for d in cursor]
    ss, qs, fs, fqs = parse_mapping(mapping)
    # first queries
    docs = qfilter.qfilter(docs, qs)

    # then function, queries
    if len(fqs.keys()):
        raise NotImplementedError("function queries are not supported [%s]"
                                  % (fqs.keys(), ))

    # then simple mapping
    rs = [{} for _ in xrange(len(docs))]
    for i in xrange(len(docs)):
        for rk, mk in ss.iteritems():
            rs[i][rk] = docs[i][mk]

    # then functions
    rs = apply_functions(docs, fs, rs)
    if asdocs:
        return rs
    rd = dict([(k, []) for k in mapping.keys()])
    for r in rs:
        for k in r.keys():
            rd[k].append(r[k])
    return rd


def test_remap
