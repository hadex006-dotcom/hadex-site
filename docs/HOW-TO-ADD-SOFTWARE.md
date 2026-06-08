# How to add software to Hadex Factory

Your site lists whatever is in `docs/software.json`. To add a program:

## The easy way (ask Claude)
Just tell Claude: "add this software" and give the file + name. Done.

## The manual way (on the GitHub website)
1. Go to your repo on github.com → open the `docs/files` folder.
2. Click **Add file → Upload files**, drag your program in (e.g. `MyApp.zip`), commit.
3. (Optional) Do the same in `docs/images` for a screenshot (e.g. `myapp.png`).
4. Open `docs/software.json`, click the ✏️ edit pencil, and add an entry inside the `[ ]`:

```json
[
  {
    "name": "My App",
    "version": "1.0",
    "description": "What it does.",
    "file": "files/MyApp.zip",
    "image": "images/myapp.png",
    "size": "12 MB"
  }
]
```

If you have more than one program, separate each `{ ... }` block with a comma.
Leave `"image"` out (or `""`) if there's no screenshot.

5. Commit. Your live site updates in ~1 minute.

## Notes
- Max single file on GitHub is 100 MB. For bigger files, use GitHub **Releases** and
  point `"file"` at the release download URL.
- `"size"` is just text shown on the card — type whatever's accurate.
