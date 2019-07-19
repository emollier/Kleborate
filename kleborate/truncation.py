"""
Copyright 2018 Kat Holt
Copyright 2018 Ryan Wick (rrwick@gmail.com)
https://github.com/katholt/Kleborate/

This file is part of Kleborate. Kleborate is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. Kleborate is distributed in
the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with Kleborate. If
not, see <http://www.gnu.org/licenses/>.
"""

from Bio.Seq import Seq
from Bio.Alphabet import IUPAC

from .misc import reverse_complement


def truncation_check(nucl_seq, strand, ref_start, ref_end, ref_length, cov_threshold=90.0):
    """
    Checks to see if the gene is truncated at the amino acid level. Returns an empty string if
    there isn't a truncation and returns a percentage (e.g. '-70%') if there is.
    """
    # BLAST gives the aligned sequence, so we might need to remove dashes if there are deletions
    # relative to the reference.
    nucl_seq = nucl_seq.replace('-', '')

    # BLAST also returns the contig's sequence so we might need to flip to the reference strand.
    if strand == 'minus':
        nucl_seq = reverse_complement(nucl_seq)
        ref_start, ref_end = ref_end, ref_start

    # The hit must start at the first base of the gene. If not, the gene is considered 0%.
    if ref_start != 1:
        return '-0%'

    # If there are any Ns in the sequence, then they will break translation, probably resulting in
    # truncation call.
    nucl_seq = nucl_seq.split('N')[0]

    # BioPython doesn't like it if the sequence isn't a multiple of 3.
    nucl_seq = nucl_seq[:len(nucl_seq) // 3 * 3]

    # The assumption is that the reference allele is a full CDS with a stop codon at the end. This
    # isn't always true (the reference sequence is sometimes broken) but will serve to make our
    # denominator for coverage.
    ref_aa_length = (ref_length - 3) // 3

    coding_dna = Seq(nucl_seq, IUPAC.unambiguous_dna)
    translation = str(coding_dna.translate(table='Bacterial', to_stop=True))

    coverage = 100.0 * len(translation) / ref_aa_length
    if coverage >= cov_threshold:
        return ''
    else:
        return '-{:.0f}%'.format(coverage)