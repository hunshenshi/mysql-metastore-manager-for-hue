Mysql元数据管理功能是一个类似hive元数据管理的管理模块，可以查看mysql数据库中的databases和tables以及修改他们的COMMENT信息。目前只支持mysql，且要使用此功能时需要配置DB query功能。

此功能是在hue3.7版本上开发的。


开启此功能需要先开启sql editor
* 将rdbMetaStore解压放入apps目录中
* 将desktop解压替换hue源码中相应的代码
* build或者注册app即可使用
