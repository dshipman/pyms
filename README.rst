===============================
pyms
===============================

PyMS - A Metastock tool for Python

David Shipman, 2012


Based in part on ms2txt by themech
https://github.com/themech/ms2txt

GPL Licensed : Please read the enclosed license in COPYING

Provides a convenient interface for accessing Metastock databases
in python (with additional support for PremiumData).

Usage:

The MSDirectory class provides an iterator over all .dat files contained
within a given path (assuming the emaster/xmaster index files are present)

If you are using PremiumData, the PremiumDataExchange class also provides
dictionary access to the underlying records.
