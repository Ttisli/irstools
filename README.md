# irstools
丽水政务云irs使用

# irstools  
**丽水政务云 IRS 工具**  
用于简化丽水政务云 IRS 系统的交互操作，支持配置管理、数据对接等功能。使用前需创建 `config.ini` 配置文件，完成基础连接信息与参数设置，确保工具正常调用政务云 IRS 服务。

## 功能简介  
- 基于配置文件实现快速对接政务云 IRS 服务；  
- 支持自定义参数配置，适配不同业务场景；  
- 提供标准化接口，便于扩展政务云相关操作。

[DATABASE]  
host = XXX.XXX.XXX.XXX  ; 数据库服务器地址
port = XXX  ; 数据库服务端口  
user = XXX  ; 数据库登录用户名  
password = ******  ; 登录密码
database = XXX ; 连接的数据库名称  

[PROXY]  
host =  ; 代理服务器地址（按需填写）  
port =  ; 代理端口（按需填写）  
user =  ; 代理认证用户名（若需认证）  
password =  ; 代理认证密码（若需认证）  

[HIGHRISKDB]  
host = XXX.XXX.XXX.XXX  ; 高风险数据库地址  
port = XXX  ; 端口  
user = XXX  ; 用户名  
password = ******  ; 密码
database = XXX  ; 数据库名称  

[DATABASE]：用于常规数据库连接，需填写地址、端口、用户名片段及数据库名，密码需严格保密，用于工具正常调用数据库服务。
[PROXY]：若通过代理访问数据库，需补全代理服务器地址、端口及认证信息（无代理时留空）。
[HIGHRISKDB]：针对高风险数据库的配置，填写地址、端口、用户名片段等信息，保障工具与目标数据库的安全连接
