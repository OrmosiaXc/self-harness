---
name: code-skill-self
description: 个人编码规范技能，适用于 Java、Kotlin、Python 项目。每当用户要求编写、修改、重构代码时，必须自动应用这套规范，无需用户重复提醒。触发词包括：写代码、实现功能、重构、新建类、创建实体、加方法、修 bug、优化代码等一切涉及代码生成或修改的场景。
---

# 个人编码规范

这是我的个人编码偏好，在所有代码生成和修改中默认遵守，不需要我每次重复说明。

## 语言要求

所有回答、解释、注释说明一律使用中文，无论用户用什么语言提问。代码中的标识符（变量名、函数名等）保持英文，但注释和对话内容用中文。

## 核心原则

**清晰优先**：代码逻辑要一眼能看懂。如果一段代码需要注释才能理解它在做什么，优先考虑重命名或拆分，而不是加注释。

**简洁优雅**：能用少的代码表达清楚的，不写多余的。避免冗余的中间变量、无意义的包装、过度的防御性代码。

## Java模块目录与Mapper资源规范

适用于本harness管理的Java后端新增模块和本次明确要求整理的模块；用户最新明确目录要求优先。此处“功能模块”指业务包目录，不等同于Maven子工程。

- 先按功能模块命名目录，再在模块目录内设置 `mapper`、`service`、`entity`；按需要增加 `controller`、`support` 等目录，不创建无内容的占位目录。禁止只在工程根包集中堆放所有模块的mapper/service/entity。
- 服务采用接口与同名 `Impl` 实现类：例如 `ProcessService` 与 `ProcessServiceImpl`。接口和实现类统一放在对应功能模块的 `service` 目录，不单独建立 `impl` 目录；调用方按接口声明依赖并注入，实现类实现对应接口。调整已有服务时同步包名、引用、注入、测试及说明文档。
- 实体、请求、响应及其他数据对象统一放在对应模块的 `entity` 目录，不另设 `domain`、`dto` 目录；类型名称和服务返回契约仍须明确，目录统一不代表必须向外暴露数据库实体。标准拼写为 `entity`。
- MyBatis Mapper Java接口和对应XML放在同一模块的同一个 `mapper` 目录，XML的namespace、类型全名与Java包名保持一致；不将XML另外放到resources/mapper。
- Maven POM参照项目已有规范，parent、dependency等标签分行书写，补齐适用的artifactId、packaging、name及parent.relativePath；直接使用的模块依赖显式声明，版本由父工程统一管理时不重复指定。
- Mapper XML位于src/main/java时，必须配置以下资源打包方式，并检查应用mapperLocations覆盖实际类路径；MapperScan也须覆盖实际接口包。标准资源目录即使暂时没有文件也保留配置。

```text
com.example.<功能模块>/
├── mapper/     # XxxMapper.java 与 XxxMapper.xml
├── service/    # XxxService.java 与 XxxServiceImpl.java，不建impl目录
└── entity/     # 实体及请求、响应等数据对象
```

```xml
<build>
    <resources>
        <resource>
            <directory>src/main/resources</directory>
            <filtering>false</filtering>
        </resource>
        <resource>
            <directory>src/main/java</directory>
            <includes>
                <include>**/*.xml</include>
            </includes>
            <filtering>false</filtering>
        </resource>
    </resources>
</build>
```

移动已有代码前先核对调用方、未提交改动和扫描配置；同步package/import、XML namespace和类型引用、资源打包及mapperLocations，不仅移动文件。既有无关模块不因新增规则而自动全量迁移。收尾检查目录和包名一致、XML与接口同目录且能被打包扫描；是否执行构建仍遵守用户授权及构建验证规则。

## 实体类构建

实体对象的创建通过自身的构造方法或 `init` 方法完成，不在外部逐个赋值属性。

**Python：**
```python
# 好
user = User(name="Alice", age=30)

# 或者工厂类方法（从外部数据源转换时）
user = User.from_dict(data)

# 避免
user = User()
user.name = "Alice"
user.age = 30
```

**Java / Kotlin：**
```kotlin
// 好 - 构造方法
val user = User(name = "Alice", age = 30)

// 避免
val user = User()
user.name = "Alice"
user.age = 30
```

## 注释规范

本次编写、生成或修改的代码须遵循以下规则：

- **实体属性**：实体、DTO、请求/响应对象及配置模型的字段或属性逐个添加简洁中文注释，说明业务含义；必要时注明单位、取值或可空条件。
- **服务方法**：服务接口和服务类中本次编写或修改的方法添加简洁中文注释，说明用途及关键行为；仅在必要时补充返回语义、异常或事务/异步完成约定，不机械复述方法名。
- Java优先使用Javadoc，Kotlin使用KDoc，Python属性使用邻近注释、方法使用docstring。Lombok等自动生成的访问器无需为添加注释改成手写代码。
- 注释通常一到两句，内容准确并随代码同步更新，避免冗长模板和逐行翻译代码。

上述实体属性和服务方法的注释是必需的；方法体内仍只对隐藏约束、业务规则、已知问题的绕过或易误解行为添加必要说明。方法体逻辑难懂时优先改善命名或拆分职责，不能依靠堆注释掩盖复杂实现。

## 避免魔法数字

用命名常量代替硬编码的数字或字符串。

```python
# 避免
if retry_count > 3:
    ...

# 好
MAX_RETRY_COUNT = 3
if retry_count > MAX_RETRY_COUNT:
    ...
```

## 函数职责

每个函数只做一件事。如果函数名里需要用"and"才能描述清楚它做了什么，考虑拆分。

方法实现尽可能简洁优雅，以易读和正确为前提：使用明确命名、适当提前返回和小范围职责拆分，减少重复逻辑、深层嵌套、冗余变量及无意义包装。优先复用已有合适能力，不为缩短行数堆叠复杂表达式、长调用链或过度抽象；保留必要的校验、异常处理、资源释放和并发控制。

## 现有代码整理

整理模块时先核对入口、调用方、接口约定和未提交改动，再删除确认无用的类、方法、参数、分支及重复实现；被其他模块或反射框架使用的代码不得仅凭本目录无调用就删除。保留必要的业务校验和异常处理。整理后的方法与实体属性按上述注释规范补齐简洁、准确的中文说明，避免用注释掩盖复杂逻辑。

## 语言特定习惯

**Python：** 优先用列表推导式、生成器表达式；用 `dataclass` 或 `pydantic` 定义数据实体；类型注解要写。

**Java / Kotlin：** Kotlin 优先用 `data class`；Java 优先用 Lombok，用 `@Data`、`@NoArgsConstructor`、`@AllArgsConstructor` 替代手写样板代码，不使用 `@Builder`；在更易读时优先用 Stream API 简化集合操作，减少 if/else 嵌套；简单循环更清晰时直接使用循环。

## 构建验证

不要主动执行 `mvn compile`、`mvn package` 等 Maven 构建命令来验证代码，除非用户明确要求验证。

## Controller 规范

- 不使用 `@PathVariable`，路径中不拼接参数
- 无参请求统一用 `@GetMapping`
- 有参请求统一用 `@PostMapping`
- 入参只用 `@RequestParam` 或 `@RequestBody`，不混用其他方式

## 模块文档生成约束

构建代码、新建模块或实现功能时，除非用户明确要求，不为每个模块新建README（包括README.md及同类模块说明入口）。必要实现说明优先维护已有设计文档、已有项目文档和任务执行记录；不以其他名称批量生成等价模块说明来绕过本规则。已有README按实际变更需要增量维护，不自动删除。
