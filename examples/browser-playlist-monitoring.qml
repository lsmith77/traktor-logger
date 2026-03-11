import QtQuick 2.0
import CSI 1.0
import "../qml/CSI/Common/Api"

/**
 * Example: Browser/Playlist Monitoring via ApiModule integration
 *
 * Publishes current browser context and selected row metadata to the logger server.
 * The payload is sent to /metadata with type="playlist" via ApiClient.sendMetadata().
 *
 * This uses ApiBrowser directly, which is also included by ApiModule.
 */
Module {
    ApiBrowser {
        pollMs: 250
    }
}
import QtQuick 2.0
import CSI 1.0
import "../qml/CSI/Common/Api"

/**
 * Example: Browser/Playlist Monitoring via ApiModule integration
 *
 * Publishes current browser context and selected row metadata to the logger server.
 * The payload is sent to /metadata with type="playlist" via ApiClient.sendMetadata().
 *
 * This uses ApiBrowser directly, which is also included by ApiModule.
 */
Module {
    ApiBrowser {
        pollMs: 250
    }
}
