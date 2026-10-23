# English common-word list

`en_common_words.txt` is every alphabetic English word whose Zipf frequency is
at least 4.5 in the `wordfreq` 3.1.1 "best" English list.

The Zipf scale was proposed by Marc Brysbaert for the SUBTLEX frequency lists.
It is the base-10 logarithm of how often a word occurs per billion words, so
4.5 sits one step below "once per 10,000 words" (Zipf 5) on that published
scale. `wordfreq` (Robyn Speer) estimates those frequencies from several
corpora rather than from one hand-written list.

- Library: <https://github.com/rspeer/wordfreq> (Apache-2.0)
- Frequency data: Creative Commons Attribution-ShareAlike 4.0
  (<https://creativecommons.org/licenses/by-sa/4.0/>)
- This file is a derivative of that data and is shared under CC-BY-SA 4.0.

No word was added or removed by hand. The file was produced by keeping tokens
from `wordfreq.iter_wordlist("en", "best")` for which `zipf_frequency` is at
least 4.5.

`en_wordfreq_words.txt` is every alphabetic token in that same list, at any
frequency. `wordfreq` 3.1.1's "best" English list is already cut at Zipf 1
(once per 100 million words on the Brysbaert scale), so the file is that
published list rather than a second hand-tuned cutoff. An all-caps token that
is not a real US listing stays prose when it appears here (ETF, CAPS) and is a
ticker candidate only when `wordfreq` does not know it at all (ZZZZQ). The
Zipf 4.5 file is the only list used to decide that a real listing is also a
common English word.
