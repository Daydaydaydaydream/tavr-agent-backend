# Qt 6 接入示例

下面是可放入 Qt 桌面项目的集成参考。本后端项目不包含 Qt 构建环境，示例未进行 C++ 编译验证。示例使用 Qt 6 的请求超时能力，Qt 5 项目应根据实际小版本适配。

## 1. 构建与头文件

在现有 CMake 工程中链接 Network（将 `your_app` 换成真实目标名）：

```cmake
find_package(Qt6 REQUIRED COMPONENTS Core Network)
target_link_libraries(your_app PRIVATE Qt6::Core Qt6::Network)
```

```cpp
#include <QDebug>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QObject>
#include <QSet>
#include <QString>
#include <QUrl>
```

## 2. 引导客户端

该类可放在头文件中，不使用自定义 Qt 信号，因此不需要 `Q_OBJECT`。请在同一个 Qt 线程中创建并调用它。它只展示提示和经过验证的动作 ID，真实页面切换需接入桌面应用。

```cpp
class GuidanceClient : public QObject {
public:
    explicit GuidanceClient(QObject *parent = nullptr)
        : QObject(parent), manager_(new QNetworkAccessManager(this)) {}

    // 每次真实软件状态变化都调用，即使暂时不发请求。
    void invalidateState() { ++generation_; }

    void requestGuidance(const QString &page, bool ctLoaded,
                         bool annulusConfirmed, bool measurementCompleted) {
        // 同一状态连续请求时，也只保留最新请求的结果。
        const quint64 requestGeneration = ++generation_;
        QNetworkRequest request{QUrl(QStringLiteral(
            "http://127.0.0.1:8000/agent/guide"))};
        request.setHeader(QNetworkRequest::ContentTypeHeader,
                          QStringLiteral("application/json"));
        request.setTransferTimeout(3000); // 传输无进展超时，不是请求总时限。

        const QJsonObject state{
            {"current_page", page},
            {"ct_loaded", ctLoaded},
            {"annulus_plane_confirmed", annulusConfirmed},
            {"measurement_completed", measurementCompleted}
        };
        const QJsonObject body{{"state", state}};
        QNetworkReply *reply = manager_->post(
            request, QJsonDocument(body).toJson(QJsonDocument::Compact));

        QObject::connect(reply, &QNetworkReply::finished, this,
                         [this, reply, requestGeneration]() {
            const QByteArray bytes = reply->readAll();
            const int status = reply->attribute(
                QNetworkRequest::HttpStatusCodeAttribute).toInt();
            const auto error = reply->error();
            const QString errorText = reply->errorString();
            reply->deleteLater();

            if (requestGeneration != generation_) return;

            if (status == 422) {
                qWarning() << "Invalid guidance request; check field names and types";
                return; // 修正客户端请求，不重试相同错误请求。
            }
            if (error != QNetworkReply::NoError || status != 200) {
                qWarning() << "Guidance unavailable" << status << errorText;
                return; // 在 UI 显示暂不可用，并允许用户重新请求。
            }

            QJsonParseError parseError;
            const QJsonDocument document = QJsonDocument::fromJson(bytes, &parseError);
            if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
                qWarning() << "Invalid guidance JSON";
                return;
            }
            const QJsonObject result = document.object();
            const QJsonValue message = result.value("message");
            const QJsonValue action = result.value("next_action");
            if (!message.isString() || !result.contains("next_action") ||
                !(action.isNull() || action.isString())) {
                qWarning() << "Invalid guidance response fields";
                return;
            }

            const QSet<QString> allowedActions{
                QStringLiteral("open_ct_import"),
                QStringLiteral("open_annulus_plane"),
                QStringLiteral("open_measurement")
            };
            if (action.isString() && !allowedActions.contains(action.toString())) {
                qWarning() << "Unsupported guidance action";
                return;
            }

            qInfo().noquote() << message.toString(); // 替换为 UI 提示。
            if (action.isNull()) return;
            qInfo() << "Suggested action:" << action.toString();
            // 将动作映射到显式注册的页面入口，可显示“前往”按钮。
            // 用户点击时再次核对状态；不要把字符串当脚本或命令执行。
        });
    }

private:
    QNetworkAccessManager *manager_;
    quint64 generation_ = 0;
};
```

## 3. 接入约定

- 由窗口或控制器持有一个 `GuidanceClient`，不要在每次调用时创建临时实例。
- CT 切换、平面修改或测量状态变化时立即调用 `invalidateState()`，清除旧提示；需要新建议时再调用 `requestGuidance()`。
- 更新 CT 后，客户端应按真实流程重置下游标志；后端不会替客户端修改状态。
- 请求成功仅表示得到建议，不能据此将操作标记为完成。
- 当前只输出日志。UI 消息、按钮启用状态、页面跳转和用户反馈应在 Qt 项目中接线并测试。
- `next_action = null` 表示不执行后续导航；未知动作也不执行。

## 4. 联调清单

1. 启动后端，确认 `GET /health` 返回 200。
2. 发送 `ctLoaded=true, annulusConfirmed=false, measurementCompleted=false`，确认返回定位模块动作。
3. 发送三个 true，确认显示完成提示且不导航。
4. 停止后端，确认网络失败后窗口仍可操作。
5. 在响应返回前切换 CT 或状态，确认旧建议被丢弃。
6. 实际连接三个模块入口，确认导航不会错误地修改完成标志。

参考：[Qt 请求与传输超时](https://doc.qt.io/qt-6/qnetworkrequest.html#setTransferTimeout)、[QNetworkAccessManager](https://doc.qt.io/qt-6/qnetworkaccessmanager.html)。若需要严格的请求总时限，应额外使用定时器并在到期时取消尚未结束的 reply。
