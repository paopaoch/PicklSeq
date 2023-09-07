import math
import subprocess
import re
import pickle
import sys
import argparse
import os

current_file = os.path.abspath(__file__)
current_directory = os.path.dirname(current_file)

# ---------- Take arguments---------------
parser = argparse.ArgumentParser(description='A script to trim DNA sequences')
parser.add_argument('-f', '--file', help='The file name of the fastq')
parser.add_argument('-t', '--type', help='The type of the DNA sequence')
parser.add_argument('-m', '--minlength',
                    help='min length of acceptable DNA sequence')
parser.add_argument('-M', '--maxlength',
                    help='max length of acceptable DNA sequence')
parser.add_argument('-q', '--quality', help='quality of Chopper reads')
parser.add_argument('-T', '--threads', help='number of CPU threads')
parser.add_argument('-c', '--matchcount', help='number of the number of CIGAR matches')
parser.add_argument('-p', '--pad', help='pad the start of the DNA sequence when pos is not 1', action='store_true')
parser.add_argument('-k', '--keep', help='keep subprocess file output', action='store_true')
args = parser.parse_args()

# Find fastq file
if args.file != None:
    file_name = args.file
else:
    print("Failed reading fastq file, file does not exist or parameter was passed incorrectly.")
    sys.exit()

# Take seq type
if args.type != None:
    seq_type = args.type.upper()
else:
    print(f"WARNING: A sequence type was not given. Defaulting to CRT.")
    seq_type = "CRT"

if seq_type == "DHPS":
    fasta_file = f"{current_directory}/utils/DHPS.fasta"
    seq_len = 642
elif seq_type == "DHFR":
    fasta_file = f"{current_directory}/utils/DHFR.fasta"
    seq_len = 491
elif seq_type == "CRT":
    fasta_file = f"{current_directory}/utils/CRT.fasta"
    seq_len = 178
else:
    print(
        f"WARNING: The sequence type {seq_type} is not recognised by the script. Defaulting to CRT.")
    fasta_file = f"{current_directory}/utils/CRT.fasta"
    seq_len = 178

# Take chopper min length
if args.minlength != None:
    min_length = args.minlength
else:
    min_length = int(seq_len / 2)
    print(
        f"WARNING: You did not supply a min length parameter. Defaulting to half of sequence length: {min_length}.")

# Take chopper max length
if args.maxlength != None:
    max_length = args.maxlength
else:
    max_length = int(seq_len * 10)
    print(
        f"WARNING: You did not supply a max length parameter. Defaulting to 10 times sequence length: {max_length}")

# Take length quality
if args.quality != None:
    quality = args.quality
else:
    quality = 1
    print(f"WARNING: You did not supply a quality parameter. Defaulting to 1.")

# Take length threads
if args.threads != None:
    threads = args.threads
else:
    threads = math.ceil(0.5 * os.cpu_count())
    print(f"WARNING: You did not supply a threads parameter. Defaulting to {threads} out of {os.cpu_count()} available cores.")

# Take length matchcount
if args.matchcount != None:
    match_count = args.matchcount
else:
    match_count = int(seq_len / 4)
    print(f"WARNING: You did not supply a match count parameter. Defaulting to {match_count}.")


# ----------Read fasta---------------
with open(fasta_file, "r") as f:
    dna_regex = r"^[ATCG]+$"
    sequences = []
    clone_names = []
    for line in f:
        if re.match(dna_regex, line.strip()):
            sequences.append(line.strip())
        else:
            clone_names.append(line.strip()[1:])
    clone_seq_dict = {key: value for key, value in zip(clone_names, sequences)}

# ----------Run Subprocess---------------
print("\nRunning subprocess...")

process = subprocess.Popen(['bash', f"{current_directory}/utils/commands.sh", file_name,
                           fasta_file, current_directory, str(min_length), str(max_length), str(quality), str(threads)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = process.communicate()

print("#####Process Completed#####")
print("Subprocess Output:")
print(stdout.decode())
print(stderr.decode())


# ----------Start Python Trimming---------------
print("Start picklseq trimming...")

cigar_num_pattern = r"\d+"
cigar_alpha_pattern = r"[A-Z]"


def get_match_count(cigar_nums, cigar_alphas):
    output = 0
    for num, alpha in zip(cigar_nums, cigar_alphas):
        if alpha in {"M"}:
            output += int(num)
    return output

def pad_start(dna_seq, starting_postion, type):
    full_seq = clone_seq_dict[type]
    return full_seq[:starting_postion - 1] + dna_seq

data = []
with open(f"{current_directory}/sorted_alignment.txt", "r") as f:
    for line in f:
        line_array = line.split('\t')
        flag = int(line_array[1])
        dna_seq = line_array[9]
        cigar_str = line_array[5]
        pos = int(line_array[3])

        cigar_nums = re.findall(cigar_num_pattern, line_array[5])
        cigar_alphas = re.findall(cigar_alpha_pattern, line_array[5])
        if len(cigar_nums) > 0:
            if cigar_alphas[0] == 'S':
                dna_seq = dna_seq[int(cigar_nums[0]):]
            if len(dna_seq) < seq_len:
                continue
            if flag in [0, 1, 16, 2048, 2064]:
                if get_match_count(cigar_nums, cigar_alphas) > match_count:
                    if args.pad:
                        dna_seq = pad_start(dna_seq, pos, line_array[2])
                        data.append([line_array[2], cigar_str, dna_seq[:seq_len]])
                    elif pos == 1:
                        data.append([line_array[2], cigar_str, dna_seq[:seq_len]])

if not args.keep:
    os.remove(f"{current_directory}/sorted_alignment.txt")

print("Trimming done")
print("Length of data: ", len(data))

with open("output.pkl", "wb") as file:
    pickle.dump(data, file)
