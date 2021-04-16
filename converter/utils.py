import regex.regex as re


def unicodify_bytes():
    bs = (
            list(range(ord("!"), ord("~") + 1))
            + list(range(ord("¡"), ord("¬") + 1))
            + list(range(ord("®"), ord("ÿ") + 1))
    )
    cs = bs[:]
    n = 0
    for b in range(2 ** 8):
        if b not in bs:
            bs.append(b)
            cs.append(2 ** 8 + n)
            n += 1
    cs = [chr(n) for n in cs]
    return dict(zip(bs, cs))


SPLITTING_REGEX = re.compile(r"""'s|'t|'re|'ve|'m|'l l|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+""")
TOKEN_UNICODEIFIER = unicodify_bytes()
TOKEN_CACHE = {}

with open("converter/vocab.bpe", "r", encoding="utf-8") as f:
    bpe_data = f.read()
bpe_merges = [tuple(merge_str.split()) for merge_str in bpe_data.split("\n")[1:-1]]
BPE_RANKS = dict(zip(bpe_merges, range(len(bpe_merges))))


def get_pairs(word):
    pairs = set()
    prev_char = word[0]
    for char in word[1:]:
        pairs.add((prev_char, char))
        prev_char = char
    return pairs


def break_token(token: str) -> str:
    if token in TOKEN_CACHE:
        return TOKEN_CACHE[token]
    word = tuple(token)

    pairs = get_pairs(word)

    if not pairs:
        return token

    while True:
        bigram = min(pairs, key=lambda pair: BPE_RANKS.get(pair, float("inf")))
        if bigram not in BPE_RANKS:
            break
        first, second = bigram
        new_word = []
        i = 0
        while i < len(word):
            try:
                j = word.index(first, i)
                new_word.extend(word[i:j])
                i = j
            except:
                new_word.extend(word[i:])
                break

            if word[i] == first and i < len(word) - 1 and word[i + 1] == second:
                new_word.append(first + second)
                i += 2
            else:
                new_word.append(word[i])
                i += 1
        new_word = tuple(new_word)
        word = new_word
        if len(word) == 1:
            break
        else:
            pairs = get_pairs(word)

    word = " ".join(word)
    TOKEN_CACHE[token] = word
    return word


def tokenize(input_text: str) -> list[str]:
    for token in re.findall(SPLITTING_REGEX, input_text):
        token = "".join(TOKEN_UNICODEIFIER[b] for b in token.encode("utf-8"))
        for bpe_token in break_token(token).split(" "):
            yield bpe_token
