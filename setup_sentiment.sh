#!/bin/bash

# FinBERT Sentiment Analysis Setup Script
# Run this to install all required dependencies for local sentiment analysis

echo "=================================="
echo "FinBERT Sentiment Analysis Setup"
echo "=================================="
echo ""

echo "Installing PyTorch, Transformers, and Sentencepiece..."
echo "This will download ~75MB of packages"
echo ""

pip install torch transformers sentencepiece

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Dependencies installed successfully!"
    echo ""
    echo "On first run, FinBERT model will download (~500MB)"
    echo "This happens automatically when you start the app."
    echo ""
    echo "To pre-download the model now, run:"
    echo "  python -c \"from transformers import AutoTokenizer, AutoModelForSequenceClassification; AutoTokenizer.from_pretrained('ProsusAI/finbert'); AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')\""
    echo ""
    echo "You're all set! Start your app with:"
    echo "  python web/app.py"
else
    echo ""
    echo "❌ Installation failed!"
    echo "Please check the error messages above."
    exit 1
fi
