---
name: android-reverse-engineering
description: Static Android reverse engineering workflow for APK, XAPK, JAR, AAR, and decompiled Android source trees. Use when the user asks to decompile Android apps, inspect manifests, find Retrofit/OkHttp/Volley endpoints, extract API URLs or auth headers, or trace UI-to-network call flows.
---

# Android Reverse Engineering

Use static tools and decompiled source to map Android API surfaces. Do not run the app or contact endpoints.

## Workflow

1. Check tool availability: JDK, `jadx`, optional `apktool`, `dex2jar`, Vineflower.
2. Decompile APK/XAPK/JAR/AAR only with user-provided local tools.
3. Inspect manifest, permissions, activities, services, receivers, providers, and application class.
4. Trace likely flow from UI to ViewModel/Presenter/Repository/API service.
5. From the plugin root, scan decompiled source:

```bash
python3 scripts/android_api_scan.py /path/to/decompiled/sources --json-out android_api.json
```

Use `python` on Windows if `python3` is absent.

## Output

Return:

- architecture and manifest summary
- endpoint table with method, path, source file, and line
- base URLs, auth header patterns, and hardcoded URL findings
- call-flow notes when source evidence supports them
- limitations

