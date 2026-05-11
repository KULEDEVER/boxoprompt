# BOXOPROMPT

**BOXOPROMPT 2026 - KULEDEVER**

BOXOPROMPT is a free Java desktop utility suite built with standard Java libraries. It started as a terminal converter and now includes a full Swing GUI for everyday tools that often get locked behind subscriptions.

## Requirements

- Java 8 or newer to run the source-compatible GUI build
- A JDK if you want to rebuild the JAR yourself
- Internet connection only for live currency conversion

## What is included

- Unit converters for weight, length, data, area, volume, speed, and time
- Free live currency conversion using the Frankfurter public API, with an expanded practical currency list
- Text tools: case conversion, line sorting, unique lines, trimming, Base64, URL encoding
- Number tools: percentages, base conversion, and random number generation
- Developer tools: UUID generation, epoch time conversion, Java string escaping, and URL decoding
- Hash/checksum tools for text and files: MD5, SHA-1, SHA-256, SHA-512
- Secure password generator using Java's `SecureRandom`
- Loan calculator and tip/split calculator
- Date calculator for date differences and date offsets
- HEX/RGB color converter with a live swatch
- File info and checksum tools
- Local scratchpad notes
- Minimal CLI fallback with `--cli`

## Run

```bash
java -jar download/v2.x/BOXOPROMPT-v2.0.jar
```

If you are running from source:

```bash
javac src/BoxoPrompt.java
java -cp src BoxoPrompt
```

To open the small command-line fallback:

```bash
java -cp src BoxoPrompt --cli
```

## Cost

Everything in BOXOPROMPT is free to use. The app uses built-in Java features and does not depend on paid APIs, subscriptions, telemetry, or external libraries.

## Legal

Copyright (c) 2026 BOXOPROMPT - KULEDEVER. All Rights Reserved.

This software, including its source code, scripts, and associated resources, is the intellectual property of the author. You may **not** copy, redistribute, modify, or use any part of this software in any form without explicit written permission from the author.

For permission requests, contact: **boxopromptofficial@outlook.com**

Personal use only. Commercial use and redistribution in any form are strictly prohibited.

*BOXOPROMPT v2.0*
