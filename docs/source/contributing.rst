=====================
Contributing to Fixit
=====================

You're very welcome to contribute to Fixit.

Call for Contribution
---------------------
1. New Autofixer Rules that help developers write simpler, safer and more efficient code.
2. IDE and workflow integration to build Fixit into development process for better usability.
3. Bug and document fixes.
4. New feature requests.

We want to make contributing to this project as easy and transparent as
possible.

Our Development Process
=======================
This `Github repo <https://github.com/Instagram/Fixit>`_ is the source of truth and all
changes need to be reviewed in pull requests.

Pull Requests
-------------
We actively welcome your pull requests.

1. Fork the repo and create your branch from ``master``.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes by ``tox test``.
5. Make sure your code lints.
6. If you haven't already, complete the Contributor License Agreement ("CLA").

Contributor License Agreement ("CLA")
-------------------------------------
In order to accept your pull request, we need you to submit a CLA. You only need
to do this once to work on any of Facebook's open source projects.

Complete your CLA here: <https://code.facebook.com/cla>

Issues
------
We use GitHub issues to track public bugs. Please ensure your description is
clear and has sufficient instructions to be able to reproduce the issue.

Facebook has a `bounty program <https://www.facebook.com/whitehat/>`_ for the safe
disclosure of security bugs. In those cases, please go through the process
outlined on that page and do not file a public issue.

Coding Style
------------
We use Fixit, flake8, isort and black to enforce coding style.
Code can be autoformatted by ``tox -e autofix``.

License
-------
By contributing to Fixit, you agree that your contributions will be licensed
under the MIT LICENSE file in the root directory of this source tree.
