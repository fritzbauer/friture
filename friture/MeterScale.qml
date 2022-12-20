import QtQuick 2.9
import QtQuick.Layouts 1.15
import QtQuick.Shapes 1.15
import "iec.js" as IECFunctions

Item {
    id: meterScale
    implicitWidth: 16

    required property int topOffset
    required property bool twoChannels

    ListModel {
        id: scaleModel

        ListElement { dB: 100 }
        ListElement { dB: 90 }
        ListElement { dB: 80 }
        ListElement { dB: 70 }
        ListElement { dB: 60 }
        ListElement { dB: 50 }
        ListElement { dB: 40 }
        ListElement { dB: 30 }
        ListElement { dB: 20 }
        ListElement { dB: 10 }
        ListElement { dB: 0 }
    }

    Repeater {
        model: scaleModel

        Item {
            implicitWidth: 16
            x: 0
            y: pathY(dB)

            Shape {
                ShapePath {
                    strokeWidth: 1
                    strokeColor: "black"
                    startX: 0
                    startY: 0
                    PathLine { x: 2; y: 0 }
                }   
            }

            Text {
                text: Math.abs(dB)
                font.pointSize: 6
                x: 0
                width: 16
                y: -5
                height: 10
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: Text.AlignHCenter
            }

            Shape {
                visible: twoChannels

                ShapePath {
                    strokeWidth: 1
                    strokeColor: "black"
                    startX: 14
                    startY: 0
                    PathLine { x: 16; y: 0 }
                }   
            }

            function pathY(dB) {
                var iec = IECFunctions.dB_to_SPL(dB);
                return Math.round((metersLayout.height - meterScale.topOffset) * (1. - iec) + meterScale.topOffset)
            }
        }
    }
}