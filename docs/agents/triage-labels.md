# Triage labels

| Role                              | Label            |
|-----------------------------------|------------------|
| Needs maintainer evaluation       | `needs-triage`   |
| Waiting on reporter               | `needs-info`     |
| Fully specified, ready for agent  | `ready-for-agent`|
| Needs human implementation        | `ready-for-human`|
| Will not be actioned              | `wontfix`        |

To create labels in GitHub if they don't exist yet:
```bash
gh label create needs-triage --color "e4e669"
gh label create needs-info --color "d93f0b"
gh label create ready-for-agent --color "0075ca"
gh label create ready-for-human --color "008672"
gh label create wontfix --color "ffffff"
```
