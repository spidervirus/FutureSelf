#!/bin/bash

# Create fonts directory if it doesn't exist
mkdir -p fonts

# Download NotoSans Regular and Bold
curl -L -o fonts/NotoSans-Regular.ttf https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf
curl -L -o fonts/NotoSans-Bold.ttf https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf

# Download NotoColorEmoji
curl -L -o fonts/NotoColorEmoji.ttf https://github.com/googlefonts/noto-emoji/raw/main/fonts/NotoColorEmoji.ttf

# Download NotoSansSymbols
curl -L -o fonts/NotoSansSymbols-Regular.ttf https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSansSymbols/NotoSansSymbols-Regular.ttf

echo "Font files downloaded successfully!"