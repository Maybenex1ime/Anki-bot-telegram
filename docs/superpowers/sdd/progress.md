Task 1: complete (commits c57a45a..73abc90, review clean; Minor noted: OWNER_ID int-cast at import, no pytest rootdir config, kv json ensure_ascii)
Task 2: complete (commits 73abc90..fc35c94, review clean; Minor noted: 7.5-rounding test not discriminating, HARD/EASY-on-new uncovered)
Task 3: complete (commits fc35c94..d9cf249, review clean; noted: upstream pypinyin DeprecationWarning)
Task 4: complete (commits d9cf249..5dfa353, review clean; Minor noted: cleanup branch uncovered by failure test, untyped signature)
Task 5: complete (commits 5dfa353..a9410f7, review clean; Minor noted: bare list annotations, untested "file rỗng" path)
Task 6: complete (commits a9410f7..c743faa, review clean; Minor noted: local date import, total_reviews derives from card state)
Task 7: complete (commits c743faa..cac8d25, review clean; Minor noted: non-atomic card+stats commits, exists_hanzi untested)
NOTE: Tasks 8-17 manual Telegram tests deferred to user (no bot token in autonomous session); agents verify via offline build_app + handler registration checks.
Task 8: complete (commits cac8d25..72a5fd8, review clean; offline verification substituted for live Telegram test)
Task 9: complete (commits 72a5fd8..fe8a630 incl. HTML-escape fix fe8a630, re-review clean)
NOTE for Tasks 10/14: apply html.escape to card fields interpolated into parse_mode=HTML messages (same fix as Task 9).
