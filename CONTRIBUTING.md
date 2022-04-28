Please read the contribution guidelines below, before submitting your first pull request to the InvenTree codebase.

## Branches and Versioning

InvenTree roughly follow the [GitLab flow](https://docs.gitlab.com/ee/topics/gitlab_flow.html) branching style, to allow simple management of multiple tagged releases, short-lived branches, and development on the main branch.

### Version Numbering

InvenTree version numbering follows the [semantic versioning](https://semver.org/) specification.

### Master Branch

The HEAD of the "main" or "master" branch of InvenTree represents the current "latest" state of code development.

- All feature branches are merged into master
- All bug fixes are merged into master

**No pushing to master:** New featues must be submitted as a pull request from a separate branch (one branch per feature).

#### Feature Branches

Feature branches should be branched *from* the *master* branch.

- One major feature per branch / pull request
- Feature pull requests are merged back *into* the master branch
- Features *may* also be merged into a release candidate branch

### Stable Branch

The HEAD of the "stable" branch represents the latest stable release code.

- Versioned releases are merged into the "stable" branch
- Bug fix branches are made *from* the "stable" branch

#### Release Candidate Branches

- Release candidate branches are made from master, and merged into stable.
- RC branches are targetted at a major/minor version e.g. "0.5"
- When a release candidate branch is merged into *stable*, the release is tagged

#### Bugfix Branches

- If a bug is discovered in a tagged release version of InvenTree, a "bugfix" or "hotfix" branch should be made *from* that tagged release
- When approved, the branch is merged back *into* stable, with an incremented PATCH number (e.g. 0.4.1 -> 0.4.2)
- The bugfix *must* also be cherry picked into the *master* branch.

## Migration Files

Any required migration files **must** be included in the commit, or the pull-request will be rejected. If you change the underlying database schema, make sure you run `invoke migrate` and commit the migration files before submitting the PR.

*Note: A github action checks for unstaged migration files and will reject the PR if it finds any!*

## Unit Testing

Any new code should be covered by unit tests - a submitted PR may not be accepted if the code coverage for any new features is insufficient, or the overall code coverage is decreased.

The InvenTree code base makes use of [GitHub actions](https://github.com/features/actions) to run a suite of automated tests against the code base every time a new pull request is received. These actions include (but are not limited to):

- Checking Python and Javascript code against standard style guides
- Running unit test suite
- Automated building and pushing of docker images
- Generating translation files

The various github actions can be found in the `./github/workflows` directory

## Code Style

Sumbitted Python code is automatically checked against PEP style guidelines. Locally you can run `invoke style` to ensure the style checks will pass, before submitting the PR.

## Documentation

New features or updates to existing features should be accompanied by user documentation. A PR with associated documentation should link to the matching PR at https://github.com/inventree/inventree-docs/

## Translations

Any user-facing strings *must* be passed through the translation engine.

- InvenTree code is written in English
- User translatable strings are provided in English as the primary language
- Secondary language translations are provided [via Crowdin](https://crowdin.com/project/inventree)

*Note: Translation files are updated via GitHub actions - you do not need to compile translations files before submitting a pull request!*

### Python Code

For strings exposed via Python code, use the following format:

```python
from django.utils.translation import ugettext_lazy as _

user_facing_string = _('This string will be exposed to the translation engine!')
```

### Templated Strings

HTML and javascript files are passed through the django templating engine. Translatable strings are implemented as follows:

```html
{% load i18n %}

<span>{% trans "This string will be translated" %} - this string will not!</span>
```