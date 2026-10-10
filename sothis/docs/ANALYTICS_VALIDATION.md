# Sothis 0.5.0 · Party analytics

The shared Android/website interface adds Parliament seat tiles, seat-share rings, election comparisons, provincial vote bars and an interactive province map. The design adapts the ring and rounded tile geometry in the user's existing **shatter prof** Figma file (`TZWxXmVtY1CZ8z3Uau5Hfi`, nodes `51:92`, `52:244`, `52:331`). The supplied static performance curve is not plotted as election evidence. The ring export endpoint returned an unavailable page; chart geometry is rendered from live values rather than shipping that invalid asset. The app continues using its bundled **Doto** font (SIL OFL); the Figma “Chairs” text uses Pixelify Sans.

## Evidence and interpretation

- [National Assembly](https://www.parliament.gov.za/national-assembly): 2024 seat allocations, total **400**, captured 10 October 2026. ANC 159, DA 87, MK 58. The page's separate `% of Total` column is not used as seat share; rings use allocated seats / 400. Parliament roster counts also include NCOP members and remain separate.
- [Sixth Parliament composition](https://www.parliament.gov.za/press-releases/current-composition-newly-sworn-6th-parliament): 2019 allocations, total **400**. ANC 230, DA 84, EFF 44. Comparisons use election observations only; no annual results are invented between them.
- [IEC provincial results PDF](https://results.elections.org.za/home/NPEPublicReports/1335/Results%20Report/National.pdf): 2024 **Provincial Ballot**, reported 21 June 2024 at 13:51:28. Highest vote shares: ANC in seven provinces, MK in KwaZulu-Natal (45.35%), DA in Western Cape (55.30%). The map shows ballot plurality, not governing/coalition control. Provincial bars cover the 18 parties in the Parliament directory; other parties and independents also contested.
- [geoBoundaries ADM1](https://www.geoboundaries.org/api/current/gbOpen/ZAF/ADM1/): 2020 province boundaries, OCHA ROSEA / Municipal Demarcation Board, **CC BY 3.0 IGO**. Geometry is simplified for an interactive chart; holes and multipart rings are preserved. The upstream “Nothern Cape” spelling is normalised. These are visual boundaries, not surveying data.
- [ANC officials](https://www.anc1912.org.za/officials/) lists Cyril Ramaphosa as President. [Parliament's presidential election statement](https://www.parliament.gov.za/press-releases/national-assembly-elects-cyril-ramaphosa-president-elect) explains that an elected President ceases to be an Assembly member. His dossier is a separate sourced leadership entry. It does not add an MP, a seat, a guessed salary or an unmatched Parliament disclosure.

The JSON manifest keeps retrieval timestamps and SHA-256 hashes of the source HTML/PDF. Province paths and credits ship locally. Platform/source icons are local SVGs; social marks use Simple Icons (CC0, with trademark attribution), and the generic news icon uses Phosphor (MIT).

Member charts summarise four business-disclosure sections: shares, outside work, directorships/partnerships and consultancies. Labels distinguish entry text, nothing declared and missing extraction. The ring counts sections containing entry text, **not companies**. Optional ZAR bars show explicit nominal amounts from the shares section in source order. Read the original table for the associated entity. No market value, complete ownership graph or current CIPC result is inferred.

Article dates use explicit `article:published_time`, `datePublished`/`pubdate` metadata or Article/WebPage JSON-LD. Conflicting dates stay unavailable. A generic `<time>`, copyright year, modified date and search `page_age` cannot substitute for publication. News view checks at most four articles with two workers; other results offer manual lookup. The server uses its existing bounded fetcher, host restrictions, public-address checks and robots rules. Android uses bounded public HTTPS requests. Access failures remain visible. Dossier exports include date evidence, source-page hash and date-check time when retrieved.

## Election outlook and updates

No reviewed national-election forecast was available for this capture. The default outlook assigns **no win probability**. Local-election polls are excluded. National voting-intention percentages, when sourced, are labelled as intention rather than chances of winning.

To capture the official sources again:

```bash
python3 scripts/update_analytics.py
```

This command requires the project's `pypdf` dependency and public network access. It validates totals and source structure and writes atomically; a changed official page fails without silently replacing the last usable manifest. It recaptures the configured 2019/2024 sources and is **not** an automatic discovery mechanism for later election years.

To install reviewed newer election results or polling:

```bash
python3 scripts/update_analytics.py --reviewed-json /path/to/reviewed-analytics.json
```

Start from `android/app/src/main/assets/analytics-data.json`. Add a completed National Assembly allocation with `date`, `total_seats: 400`, a complete `seats` map and `source_url`; update provincial results/credits when applicable. Append polls to `polls` with:

```json
{
  "election_type": "national",
  "measure": "voting_intention",
  "target_after": "2024-05-29",
  "published_at": "2026-09-01",
  "fieldwork_from": "2026-08-01",
  "fieldwork_to": "2026-08-20",
  "expires_at": "2026-12-01",
  "publisher": "Replace with the actual publisher",
  "source_url": "https://example.org/replace-with-original-poll",
  "sample_size": 1500,
  "population": "Replace with the actual sampled population",
  "methodology": "Replace with the published sampling method and uncertainty",
  "shares": {}
}
```

This is a schema example, **not a poll**; it is not included in the app's data. Validation rejects local polls, missing provenance/sample/date information and any `win_probability` field. Give each poll a reviewed expiry. The UI selects the newest completed election, displays only polls whose `target_after` matches it, and excludes expired or future-published polls. Installing a later completed election retires the old cycle's outlook without a UI edit. The engine rereads the manifest on `/api/analytics`; connected clients refresh at most every five minutes when visiting Party. A rebuilt Android app replaces its offline capture. Rebuild/redeploy the website container to replace its bundled manifest.

## Verification

Validated 10 October 2026:

- **55 Python tests passed.** They cover source totals, nine provinces, official result anchors, invalid manifests, poll scope/date checks, data replacement without a process restart, leadership separation, publication/modified-date distinction, conflicts and authenticated API/static boundaries.
- Browser tests exercise the 400 tiles, province selections, seat/ring/footprint charts, Ramaphosa, business section status, source icons, manual and automatic publication dates, browser history, the Android back handler and a **file-origin native bridge**, including returning to the root screen.
- Layouts checked at 320, 390, 720 and 1280 px, with no horizontal overflow. Existing UI suites additionally check all main screens, evidence pinning, exports, alerts, provider failure and six viewport widths.
- The authenticated WSGI website flow checks actual sessions/CSRF, the analytics endpoint/assets, ANC leadership and browser Back, alongside existing search/case/export/alert/reload/logout behavior.
- Android 0.5.0, versionCode 6, is compiled against SDK 35 (minimum 26) and signed using the same development key. APK signatures and signer continuity are checked. No physical-device/emulator gesture or installation is claimed.

Provider/article calls in browser tests use controlled fixtures; tests prove parsing, UI behavior and provenance labels, not all external providers' uptime. Screenshots with article dates are fixture-based demonstrations. No server or Cloudflare DNS change was made in this update.

Reproduce:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/check_ui.py --chrome /path/to/chrome --playwright /path/to/playwright
python3 scripts/check_web.py --chrome /path/to/chrome --playwright /path/to/playwright
```

The existing self-hosting instructions remain in [deploy/README.md](../deploy/README.md).
