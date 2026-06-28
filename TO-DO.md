Do not do these automatically, this list requires input from a claude code window, will manually approve each item





\*\*1

Please modify ClamBakeSanta so generated haikus are validated before caching or posting.



Add a Python syllable validator using CMU/pronouncing with a fallback heuristic.



Requirements:

\- Validate each haiku as exactly 5-7-5.

\- Run validation before writing state/haiku\_cache.json.

\- If invalid, retry generation or rewrite up to 5 times.

\- If still invalid, fail the GitHub Action before any adapters post.

\- Add a standalone script scripts/validate\_haiku.py that can validate state/haiku\_cache.json.

\- Update daily.yml to run validation before publishing.

\- Log each failed count like: expected 5-7-5, got 5-8-5.

\- Prefer simple words and avoid ambiguous syllable words in the generation prompt.



\*\*2

Add Wordpress to the engagement check, verify all sources are having their engagement looked at



\*\*3

Clean up the filesystem, there are scripts at the root, make it clean and tidy and make sense



\*\*4

For each file, run the script through an outside AI model and have the script verified and see if there are any recommendations



\*\*5

Update the Changelog and the Gitpages, keep the website in line



\*\*6

Build a CLAUDE.md file that will get things up and running and understood when I open a new Claude Code window, including checkout/checkin with GitHub, updating Changelog in the README.md, and keeping the website coherent



\*\*7

Ideas for more Haikus...



Moon Phases (python script)

Seasons Changing

On This Day In History

zodiac





