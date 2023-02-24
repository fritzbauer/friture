import QtQuick 2.9
import QtQuick.Layouts 1.15
import QtQuick.Shapes 1.15
import "iec.js" as IECFunctions

Item {
    id: meterScale
    objectName: "meterScale"
    implicitWidth: 16

    required property int topOffset
    required property bool twoChannels
    property var scaleMode

    function setScaleMode(mode) {
        scaleMode = mode
        if(mode == "RMS") {
            scaleModel.set(10,{ dB: 0 })
            scaleModel.set(9, { dB: 0 })
            scaleModel.set(8, { dB: 0 })
            scaleModel.set(7, { dB: -3 })
            scaleModel.set(6, { dB: -6 })
            scaleModel.set(5, { dB: -10 })
            scaleModel.set(4, { dB: -20 })
            scaleModel.set(3, { dB: -30 })
            scaleModel.set(2, { dB: -40 })
            scaleModel.set(1, { dB: -50 })
            scaleModel.set(0, { dB: -60 })
        } else {
            scaleModel.set(10, {dB: 11})
            scaleModel.set(9,  {dB: 22})
            scaleModel.set(8,  {dB: 33})
            scaleModel.set(7,  {dB: 40})
            scaleModel.set(6,  {dB: 50})
            scaleModel.set(5,  {dB: 60})
            scaleModel.set(4,  {dB: 70})
            scaleModel.set(3,  {dB: 80})
            scaleModel.set(2,  {dB: 90})
            scaleModel.set(1,  {dB: 100})
        }
    }

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
                var iec
                if(scaleMode == "RMS") {
                    iec = IECFunctions.dB_to_IEC(dB);
                } else {
                    iec = IECFunctions.dB_to_SPL(dB);
                }
                return Math.round((metersLayout.height - meterScale.topOffset) * (1. - iec) + meterScale.topOffset)
            }
        }
    }
}