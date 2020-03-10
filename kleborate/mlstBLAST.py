#!/usr/bin/env python3
"""
Reports best match
  * :   best matching allele is not precise match
 -nLV : best matching ST is n-locus variant

If an annotation column is provided (such as clonal complex) in the final column of the profiles
file, this annotation will be reported in column 2 of the output table.

Copyright 2020 Kat Holt
Copyright 2020 Ryan Wick (rrwick@gmail.com)
https://github.com/katholt/Kleborate/

This file is part of Kleborate. Kleborate is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. Kleborate is distributed in
the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with Kleborate. If
not, see <http://www.gnu.org/licenses/>.
"""

import collections
import os
import re

from .blastn import run_blastn
from .truncation import truncation_check


def mlst_blast(seqs, database, info_arg, assemblies, min_cov, min_ident, max_missing,
               check_for_truncation=False, report_incomplete=False, allow_multiple=False):
    st_names, alleles_to_st, st_to_info, header = load_st_database(database, info_arg)

    # In order to call an ST, there needs to be an exact match for half (rounded down) of the
    # relevant alleles.
    required_exact_matches = int(len(header) / 2)

    contigs = assemblies[0]
    _, filename = os.path.split(contigs)
    name, _ = os.path.splitext(filename)

    hits = run_blastn(seqs, contigs, min_cov, min_ident)
    if not allow_multiple:
        hits = keep_only_one_hit_per_locus(hits)

    best_allele = get_best_allele_per_locus(hits, check_for_truncation)

    best_st = []
    best_st_annotated = []

    mismatch_loci_including_snps, missing_loci = 0, 0

    for locus in header:
        if locus in best_allele:
            allele = best_allele[locus]

            # Remove * (inexact match) and truncation percentages
            allele_number = allele.replace('*', '')
            allele_number = re.sub(r'-\d+%', '', allele_number)

            if '*' in allele:
                mismatch_loci_including_snps += 1
            best_st.append(allele_number)
            best_st_annotated.append(allele)  # will still have character if imperfect match
        else:
            best_st.append('-')
            best_st_annotated.append('-')
            mismatch_loci_including_snps += 1
            missing_loci += 1

    # assign ST
    bst = ','.join(best_st)

    if mismatch_loci_including_snps <= max_missing:
        # only report ST if enough loci are precise matches
        if bst in alleles_to_st:
            # note may have mismatching alleles due to SNPs, this will be recorded in
            # mismatch_loci_including_snps
            bst = alleles_to_st[bst]
        else:
            # determine closest ST
            bst, _, mismatch_loci_including_snps = \
                get_closest_locus_variant(best_st, best_st_annotated, alleles_to_st)
    else:
        bst = '0'

    exact_matches = len(best_st) - mismatch_loci_including_snps
    if exact_matches < required_exact_matches:
        bst = '0'

    # pull info column
    info_final = ''
    if info_arg == 'yes' and bst in st_to_info:
        info_final = st_to_info[bst]
        if report_incomplete and missing_loci > 0:
            info_final += ' (incomplete)'

    if mismatch_loci_including_snps > 0 and bst != '0':
        bst += '-' + str(mismatch_loci_including_snps) + 'LV'

    return bst, best_st_annotated, info_final


def get_allele_and_locus(hit):
    """
    Parses the allele name and locus name from the hit's gene ID.
    """
    if '__' in hit.gene_id:  # srst2 formatted file
        gene_id_components = hit.gene_id.split('__')
        locus = gene_id_components[1]
        allele = gene_id_components[2]
    else:
        allele = hit.gene_id
        locus = hit.gene_id.split('_')[0]
    return allele, locus


def keep_only_one_hit_per_locus(hits):
    hits_per_locus = collections.defaultdict(list)
    for hit in hits:
        _, locus = get_allele_and_locus(hit)
        hits_per_locus[locus].append(hit)
    kept_hits = []
    for locus, locus_hits in hits_per_locus.items():
        locus_hits = sorted(locus_hits, key=lambda x: x.score, reverse=True)  # sort best to worst
        best_hit = locus_hits[0]
        kept_hits.append(best_hit)
    return kept_hits


def get_best_allele_per_locus(hits, check_for_truncation):
    best_score = {}   # key = locus, value = BLAST score for best allele encountered so far
    best_allele = {}  # key = locus, value = best allele (* if imprecise match)

    for hit in hits:
        allele, locus = get_allele_and_locus(hit)
        if hit.pcid < 100.00 or hit.alignment_length < hit.ref_length:
            allele += '*'  # inexact match
        if check_for_truncation:
            allele += truncation_check(hit)[0]
        # store best match for each one locus
        if locus in best_score:
            if hit.score > best_score[locus]:    # update
                best_score[locus] = hit.score
                best_allele[locus] = allele.split('_')[1]  # store number only
        else:  # initialise
            best_score[locus] = hit.score
            best_allele[locus] = allele.split('_')[1]  # store number only

    return best_allele


def load_st_database(database, info_arg):
    st_names = []
    alleles_to_st = {}  # key = concatenated string of alleles, value = st
    st_to_info = {}  # key = st, value = info relating to this ST, eg clonal group
    header = []
    with open(database, 'r') as f:
        for line in f:
            fields = line.rstrip().split('\t')
            if len(header) == 0:
                header = fields
                header.pop(0)  # remove st label
                if info_arg == 'yes':
                    header.pop()  # remove info label
            else:
                st = fields.pop(0)
                if info_arg == 'yes':
                    info = fields.pop()
                else:
                    info = ''
                st_names.append(st)
                alleles_to_st[','.join(fields)] = st
                if info_arg == 'yes':
                    st_to_info[st] = info
    return st_names, alleles_to_st, st_to_info, header


def get_closest_locus_variant(query, annotated_query, sts):
    annotated_query = list(annotated_query)  # copy the list so we don't change the original
    closest = []
    closest_alleles = {}   # key = st, value = list
    min_dist = len(query)  # number mismatching loci, ignoring SNPs

    for index, item in enumerate(query):
        if item == '-':
            query[index] = '0'

    # get distance from closest ST, ignoring SNPs
    for st in sts:
        d = sum(map(lambda x, y: bool(int(x)-int(y)), st.split(','), query))
        if d == min_dist:
            closest.append(int(sts[st]))
            closest_alleles[sts[st]] = st
        elif d < min_dist:
            # reset
            closest = [int(sts[st])]
            closest_alleles[sts[st]] = st
            min_dist = d  # distance from closest ST, ignoring SNPs

    closest_st = str(min(closest))

    for index, item in enumerate(annotated_query):
        annotated_query[index] = re.sub(r'-\d+%', '', item)
        if item == '-' or '*' in item:
            annotated_query[index] = '0'

    # get distance from closest ST, including SNPs
    min_dist_incl_snps = sum(map(lambda x, y: bool(int(x)-int(y)),
                                 closest_alleles[closest_st].split(','), annotated_query))

    return closest_st, min_dist, min_dist_incl_snps
