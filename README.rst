.. image:: docs/_static/logo/logo.svg
   :width: 600 px
   :alt: Fixit

|readthedocs-badge| |pypi-badge| |changelog-badge| |license-badge|

.. |readthedocs-badge| image:: https://readthedocs.org/projects/pip/badge/?version=latest&style=flat
   :target: https://fixit.readthedocs.io/en/latest/
   :alt: Documentation

.. |pypi-badge| image:: https://img.shields.io/pypi/v/fixit.svg
   :target: https://pypi.org/project/fixit
   :alt: PyPI

.. |changelog-badge| image:: https://img.shields.io/badge/change-log-blue.svg
   :target: https://fixit.readthedocs.io/en/latest/changelog.html
   :alt: Changelog

.. |license-badge| image:: https://img.shields.io/pypi/l/fixit.svg
   :target: https://github.com/instagram/fixit/blob/main/LICENSE
   :alt: MIT License

Fixit provides a highly configurable linting framework with support for
auto-fixes, custom "local" lint rules, and hierarchical configuration, built
on `LibCST <https://libcst.rtfd.io>`_.

Fixit makes it quick and easy to write new lint rules and offer suggested
changes for any errors found, which can then be accepted automatically,
or presented to the user for consideration.


**Fixit has been rebuilt for better configuration and support for custom
lint rules.** If you are using Fixit 0.1.4 or older, take a look at the
`legacy documentation <https://fixit.rtfd.io/en/v0.1.4/>`_
or the `stable branch <https://github.com/Instagram/Fixit/tree/0.x>`_.


.. include:: guide/quickstart.rst
.. include:: docs/guide/quickstart.rst

For more details, see the `user guide`__.

.. __: https://fixit.rtfd.io/en/latest/guide.html


License
-------

Fixit is `MIT licensed`__, as found in the LICENSE file.

.. __: https://github.com/Instagram/Fixit/blob/main/LICENSE
