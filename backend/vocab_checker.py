import json
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

VOCAB_DIR = Path(__file__).resolve().parent.parent / "vocabulary_data"
VOCAB_PATH = VOCAB_DIR / "kaoyan_5500.json"

# ── Simple rule-based lemmatizer ──────────────────────────────────────
# Handles common English morphology without external deps

_IRREGULAR = {
    # be
    "is": "be", "am": "be", "are": "be", "was": "be", "were": "be",
    "been": "be", "being": "be",
    # have
    "has": "have", "had": "have", "having": "have",
    # do
    "did": "do", "does": "do", "done": "do", "doing": "do",
    # say
    "said": "say", "says": "say", "saying": "say",
    # make
    "made": "make", "makes": "make", "making": "make",
    # take
    "taken": "take", "takes": "take", "taking": "take",
    # give
    "given": "give", "gives": "give", "giving": "give",
    # write
    "written": "write", "writes": "write", "writing": "write",
    "wrote": "write",
    # eat
    "eaten": "eat", "eats": "eat", "eating": "eat",
    "ate": "eat",
    # speak
    "spoken": "speak", "speaks": "speak", "speaking": "speak",
    "spoke": "speak",
    # break
    "broken": "break", "breaks": "break", "breaking": "break",
    "broke": "break",
    # drive
    "driven": "drive", "drives": "drive", "driving": "drive",
    "drove": "drive",
    # ride
    "ridden": "ride", "rides": "ride", "riding": "ride",
    "rode": "ride",
    # rise
    "risen": "rise", "rises": "rise", "rising": "rise",
    "rose": "rise",
    # freeze
    "frozen": "freeze", "freezes": "freeze", "freezing": "freeze",
    "froze": "freeze",
    # choose
    "chosen": "choose", "chooses": "choose", "choosing": "choose",
    "chose": "choose",
    # steal
    "stolen": "steal", "steals": "steal", "stealing": "steal",
    "stole": "steal",
    # wake
    "woken": "wake", "wakes": "wake", "waking": "wake",
    "woke": "wake",
    # forget
    "forgotten": "forget", "forgets": "forget", "forgetting": "forget",
    "forgot": "forget",
    # hide
    "hidden": "hide", "hides": "hide", "hiding": "hide",
    # begin
    "begun": "begin", "begins": "begin", "beginning": "begin",
    "began": "begin",
    # swim
    "swum": "swim", "swims": "swim", "swimming": "swim",
    "swam": "swim",
    # sink
    "sunk": "sink", "sinks": "sink", "sinking": "sink",
    "sank": "sink",
    # sing
    "sung": "sing", "sings": "sing", "singing": "sing",
    "sang": "sing",
    # ring
    "rung": "ring", "rings": "ring", "ringing": "ring",
    "rang": "ring",
    # spring
    "sprung": "spring", "springs": "spring", "springing": "spring",
    "sprang": "spring",
    # shrink
    "shrunk": "shrink",
    # comparatives / superlatives
    "bigger": "big", "biggest": "big",
    "better": "good", "best": "good",
    "worse": "bad", "worst": "bad",
    "more": "much", "most": "much",
    "less": "little", "least": "little",
    "earlier": "early", "earliest": "early",
    "easier": "easy", "easiest": "easy",
    "happier": "happy", "happiest": "happy",
    "busier": "busy", "busiest": "busy",
    # run
    "ran": "run", "runs": "run", "running": "run",
    # drink
    "drank": "drink", "drinks": "drink", "drinking": "drink",
    # see
    "saw": "see", "sees": "see", "seeing": "see",
    # know
    "knew": "know", "knows": "know", "knowing": "know",
    # draw
    "drew": "draw", "draws": "draw", "drawing": "draw",
    # grow
    "grew": "grow", "grows": "grow", "growing": "grow",
    # throw
    "threw": "throw", "throws": "throw", "throwing": "throw",
    # fly
    "flew": "fly", "flies": "fly", "flying": "fly",
    # go
    "went": "go", "goes": "go", "going": "go",
    # lie
    "lay": "lie", "lies": "lie", "lying": "lie",
    # pay
    "paid": "pay", "pays": "pay", "paying": "pay",
    # build
    "built": "build", "builds": "build", "building": "build",
    # send
    "sent": "send", "sends": "send", "sending": "send",
    # bend
    "bent": "bend", "bends": "bend", "bending": "bend",
    # spend
    "spent": "spend", "spends": "spend", "spending": "spend",
    # leave
    "left": "leave", "leaves": "leave", "leaving": "leave",
    # lose
    "lost": "lose", "loses": "lose", "losing": "lose",
    # feel
    "felt": "feel", "feels": "feel", "feeling": "feel",
    # keep
    "kept": "keep", "keeps": "keep", "keeping": "keep",
    # sleep
    "slept": "sleep", "sleeps": "sleep", "sleeping": "sleep",
    # meet
    "met": "meet", "meets": "meet", "meeting": "meet",
    # sit
    "sat": "sit", "sits": "sit", "sitting": "sit",
    # hit / put / cut / set / let / read (unchanged forms)
    "hits": "hit", "hitting": "hit",
    "puts": "put", "putting": "put",
    "cuts": "cut", "cutting": "cut",
    "sets": "set", "setting": "set",
    "lets": "let", "letting": "let",
    "reads": "read", "reading": "read",
    # lead
    "led": "lead", "leads": "lead", "leading": "lead",
    # hold
    "held": "hold", "holds": "hold", "holding": "hold",
    # think
    "thought": "think", "thinks": "think", "thinking": "think",
    # bring
    "brought": "bring", "brings": "bring", "bringing": "bring",
    # buy
    "bought": "buy", "buys": "buy", "buying": "buy",
    # fight
    "fought": "fight", "fights": "fight", "fighting": "fight",
    # catch
    "caught": "catch", "catches": "catch", "catching": "catch",
    # teach
    "taught": "teach", "teaches": "teach", "teaching": "teach",
    # find
    "found": "find", "finds": "find", "finding": "find",
    # bind / wind / grind
    "bound": "bind", "binds": "bind", "binding": "bind",
    "wound": "wind", "winds": "wind", "winding": "wind",
    "ground": "grind", "grinds": "grind", "grinding": "grind",
    # stand
    "stood": "stand", "stands": "stand", "standing": "stand",
    "understood": "understand", "understands": "understand",
    # get
    "got": "get", "gets": "get", "getting": "get",
    # win
    "won": "win", "wins": "win", "winning": "win",
    # become
    "became": "become", "becomes": "become", "becoming": "become",
    # come
    "came": "come", "comes": "come", "coming": "come",
    # tell
    "told": "tell", "tells": "tell", "telling": "tell",
    # sell
    "sold": "sell", "sells": "sell", "selling": "sell",
    # fall
    "fell": "fall", "falls": "fall", "falling": "fall",
    # tear
    "tore": "tear", "tears": "tear", "tearing": "tear",
    # wear
    "wore": "wear", "wears": "wear", "wearing": "wear",
    # -ize → -is derivations
    "emphasize": "emphasis", "emphasizes": "emphasis", "emphasizing": "emphasis",
    "hypothesize": "hypothesis",
    "synthesize": "synthesis",
    "analyze": "analysis", "analyzes": "analysis", "analyzing": "analysis",
}

_SUFFIX_RULES = [
    (r"ily$", "y"),      # happily → happy
    (r"iness$", "y"),    # happiness → happy (before generic "ness")
    (r"iness$", ""),     # happiness → happine (fallback)
    (r"ies$", "y"),      # studies → study
    (r"ves$", "f"),      # wolves → wolf
    (r"ization$", "ize"),# organization → organize
    (r"isation$", "ise"),# organisation → organise
    (r"es$", ""),        # catches → catch
    (r"ing$", ""),       # making → mak, running → run
    (r"ed$", ""),        # sparked → spark, baked → bak
    (r"ly$", ""),        # quickly → quick
    (r"ment$", ""),      # treatment → treat
    (r"tion$", "te"),    # education → educate
    (r"tion$", ""),      # action → act
    (r"sion$", "de"),    # division → divide
    (r"sion$", ""),      # mission → miss
    (r"ness$", ""),      # darkness → dark
    (r"ity$", ""),       # capacity → capac
    (r"er$", ""),        # bigger → bigg, later → lat
    (r"est$", ""),       # biggest → bigg, latest → lat
    (r"s$", ""),         # dogs → dog
]


def lemmatize(word: str) -> str:
    """Reduce word to base form. Handles common English morphology."""
    w = word.lower().strip(".,!?;:\"'()[]{}「」『』【】《》")
    if not w or len(w) <= 1:
        return w
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    for pattern, replacement in _SUFFIX_RULES:
        # Only strip -s if word is long enough to avoid has→ha, is→i
        if pattern == r"s$" and len(w) <= 3:
            continue
        candidate = re.sub(pattern, replacement, w)
        if candidate != w:
            return candidate
    return w


_PREFIXES = ["un", "mis", "re", "over", "under", "dis", "pre", "non", "in", "im", "il", "ir"]


def lemmatize_candidates(word: str) -> list[str]:
    """Return multiple possible base forms. Used for fuzzy matching."""
    w = word.lower().strip(".,!?;:\"'()[]{}「」『』【】《》")
    if not w or len(w) <= 1:
        return [w]
    if w in _IRREGULAR:
        return [w, _IRREGULAR[w]]
    candidates = [w]
    # Strip common prefixes
    for prefix in _PREFIXES:
        if w.startswith(prefix) and len(w) > len(prefix) + 2:
            candidates.append(w[len(prefix):])
    # Apply suffix rules
    for pattern, replacement in _SUFFIX_RULES:
        if pattern == r"s$" and len(w) <= 3:
            continue
        candidate = re.sub(pattern, replacement, w)
        if candidate != w:
            candidates.append(candidate)
            # For -ing and -ed, also try adding back trailing e
            if pattern in (r"ing$", r"ed$"):
                candidates.append(candidate + "e")
            # For -er and -est, try removing double consonant
            if pattern in (r"er$", r"est$") and len(candidate) >= 3 and candidate[-1] == candidate[-2]:
                candidates.append(candidate[:-1])
    # Also try stripping prefix THEN suffix
    for prefix in _PREFIXES:
        if w.startswith(prefix) and len(w) > len(prefix) + 2:
            stripped = w[len(prefix):]
            if stripped not in candidates:
                candidates.append(stripped)
            for pattern, replacement in _SUFFIX_RULES:
                if pattern == r"s$" and len(stripped) <= 3:
                    continue
                suffix_cand = re.sub(pattern, replacement, stripped)
                if suffix_cand != stripped:
                    candidates.append(suffix_cand)
    return list(dict.fromkeys(candidates))  # unique, preserve order


class VocabChecker:
    """考研5500词库校验器。"""

    def __init__(self, vocab_path: str | Path = VOCAB_PATH):
        self.vocab_path = Path(vocab_path)
        self.vocab_set: set[str] = set()
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        if not self.vocab_path.exists():
            raise FileNotFoundError(f"Vocab file not found: {self.vocab_path}")
        with open(self.vocab_path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            word = item.get("word", "").strip().lower()
            if word:
                self.vocab_set.add(word)
                self.vocab_set.add(lemmatize(word))
        logger.info(f"Loaded {len(data)} words, {len(self.vocab_set)} lemmatized forms")
        self._loaded = True

    def is_in_vocab(self, word: str) -> bool:
        """Check if word or any of its possible base forms is in the 5500 list."""
        w = word.strip(".,!?;:\"'()[]{}「」『』【】《》")
        if not w or len(w) <= 1:
            return True
        w_lower = w.lower()
        if w_lower in self.vocab_set:
            return True
        # Check all candidate lemmas (recursively lemmatize each candidate too)
        for cand in lemmatize_candidates(w):
            if cand in self.vocab_set:
                return True
            # Recursive: also check lemmatized form of the candidate
            cand_lemma = lemmatize(cand)
            if cand_lemma != cand and cand_lemma in self.vocab_set:
                return True
        return False

    def is_proper_noun(self, word: str, sentence_start: bool = False) -> bool:
        """Heuristic proper noun detection."""
        w = word.strip(".,!?;:\"'()[]{}")
        if not w or len(w) <= 1:
            return False
        if not w[0].isupper():
            return False
        if sentence_start:
            return False
        # All caps: acronym
        if w.isupper() and len(w) <= 6:
            return True
        # Capitalized but not sentence start: likely proper noun
        return True

    def detect_oov(self, tokens: list[str]) -> list[dict]:
        """Return list of {word, lemma, position} for out-of-vocabulary words."""
        oov = []
        for i, token in enumerate(tokens):
            clean = token.strip(".,!?;:\"'()[]{}「」『』【】《》")
            if not clean or len(clean) <= 1:
                continue
            sentence_start = (i == 0) or (tokens[i - 1] in (".", "!", "?", "..."))
            if self.is_proper_noun(clean, sentence_start):
                continue
            if not self.is_in_vocab(clean):
                oov.append({
                    "word": clean,
                    "lemma": lemmatize(clean),
                    "position": i,
                })
        return oov

    def oov_ratio(self, tokens: list[str]) -> float:
        """Return ratio of OOV tokens (excluding proper nouns)."""
        oov = self.detect_oov(tokens)
        if not tokens:
            return 0.0
        return len(oov) / len(tokens)
