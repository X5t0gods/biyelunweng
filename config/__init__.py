"""项目包初始化。

Django 的 MySQL 后端依赖 MySQLdb（mysqlclient）驱动。Windows 下编译 mysqlclient 较为麻烦，
这里统一使用纯 Python 实现的 PyMySQL，并通过 install_as_MySQLdb() 伪装成 MySQLdb。
若已安装 mysqlclient，可删除本文件内容，Django 会自动使用原生驱动。
"""

try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover
    pass
