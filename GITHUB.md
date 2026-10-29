# GitHub access setup

There are two separate kinds of GitHub access, and they are set up
differently:

| You want to...                                   | Set up              |
|--------------------------------------------------|---------------------|
| `git push` / `git pull`, open PRs with `gh`      | GitHub CLI (`gh`)   |
| Let Claude work with issues, PRs, repos via MCP  | GitHub MCP server   |

The GitHub MCP server does **not** give `git push` access -- git uses its
own credentials. For most work, the GitHub CLI alone is enough.

## 1. GitHub CLI (needed for `git push`)

```bash
sudo apt install gh
gh auth login        # GitHub.com -> HTTPS -> Login with a web browser
gh auth setup-git    # make git use gh's credentials
```

Check it worked:

```bash
gh auth status
cd ~/projects/shopee && git push
```

After this, `git push` works from your terminal and for Claude Code, and
`gh pr create` can open pull requests.

## 2. GitHub MCP server (optional)

`claude mcp login github` fails with:

```
SDK auth failed: Incompatible auth server: does not support dynamic client registration
```

GitHub's MCP server doesn't let clients register themselves for the
browser login, so connect it with a personal access token instead.

1. Create a token: **GitHub -> Settings -> Developer settings -> Personal
   access tokens -> Fine-grained tokens**. Give it access to
   `roachhuang/shopee` (or all repositories) and the permissions you need,
   e.g. *Contents* and *Pull requests*.
2. Add the server, running this in your own terminal so the token never
   passes through a chat. `read -rs` takes the pasted token without
   showing it; type the last line exactly as shown, including `$GH_TOKEN`:

   ```bash
   read -rs GH_TOKEN    # paste the token, press Enter (nothing is shown)
   claude mcp add --scope user --transport http github https://api.githubcopilot.com/mcp --header "Authorization: Bearer $GH_TOKEN"
   ```

   - `--scope user` makes it available in every folder. Without it, the
     server is only registered for the folder you ran the command in.
   - Keep the `claude mcp add` command on one line. A line break pasted
     into the header gives `Header 'Authorization' has invalid value`.
   - `Authorization header is badly formatted` (HTTP 400) means the header
     doesn't hold a real token, e.g. a placeholder was left in.
   - To replace the token: `claude mcp remove github -s user`, then add it
     again.

3. Check it connected:

   ```bash
   claude mcp list    # expect: github ... ✔ Connected
   ```

The token is stored in plain text in your Claude Code config. Give it an
expiry date, and revoke it on GitHub if it leaks.
