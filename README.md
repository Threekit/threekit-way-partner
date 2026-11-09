# The Threekit Way .AI, for implementation partners

For the companies Threekit works with. Your Threekit project manager gives your company access; your partner admin
puts you on projects. Then install once, in the editor you use:

Claude Code:

    claude plugin marketplace add Threekit/threekit-way-partner && claude plugin install threekit-way@threekit-partner

Cursor:

    git clone https://github.com/Threekit/threekit-way-partner.git ~/.threekit-way && bash ~/.threekit-way/tools/install-cursor.sh

Codex (the CLI, the IDE extension and the desktop app):

    git clone https://github.com/Threekit/threekit-way-partner.git ~/.threekit-way && bash ~/.threekit-way/tools/install-codex.sh

Claude (claude.ai or Cowork): download the plugin file from https://way.3kit.ai/partner after signing in, then Customize,
Plugins, Upload plugin.

The first session shows a link to https://way.3kit.ai/connect: sign in with the code sent to your email, press Connect this
computer, copy the key and paste it in the chat. The skills then read the method from the dashboard, kept current
every day. When your sign-in ends, the editor shows the link again. This repository holds no method: only the
plugin's scripts and hooks, and each skill's first line.
