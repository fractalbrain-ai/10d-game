API reference
=============

Package metadata
----------------

.. py:data:: xdgame.__version__
   :type: str

   Shared version of the Python binding and WebAssembly engine, which are kept
   in sync. When a game is initialized, the binding verifies that the loaded
   engine has this version.

Game
----

.. autoclass:: xdgame.Game
   :members:

Gym-style environment
---------------------

.. autoclass:: xdgame.XDGameEnv
   :members:

Configuration
-------------

.. autofunction:: xdgame.default_config

.. autofunction:: xdgame.config_from_toml

.. autoclass:: xdgame.Config
   :members:

.. autoclass:: xdgame.BeanVariants

Actions
-------

.. autoclass:: xdgame.Action

Exceptions
----------

.. autoexception:: xdgame.XDGameError
