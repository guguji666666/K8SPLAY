#!/bin/bash
# Push Recovery Feature and Create PR

set -e

echo "🚀 Pushing Recovery Feature to GitHub..."
echo ""

# Add SSH key if not already added
ssh-add ~/.ssh/id_rsa 2>/dev/null || true

# Push to remote
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Push successful!"
    echo ""
    echo "📝 To create PR, run:"
    echo "   gh pr create --title 'feat: Add recovery verification with persistent issue detection' --body-file RECOVERY_FEATURE_PR.md"
    echo ""
    echo "Or visit: https://github.com/guguji666666/K8SPLAY/compare/main...main"
else
    echo ""
    echo "❌ Push failed. Try:"
    echo "   1. Check SSH connection: ssh -T git@github.com"
    echo "   2. Add SSH key: ssh-add ~/.ssh/id_rsa"
    echo "   3. Pull latest changes: git pull origin main"
    echo "   4. Then retry: git push origin main"
fi
