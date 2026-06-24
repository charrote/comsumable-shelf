import React, { useState, useEffect, useCallback } from 'react'
import {
  View, Text, TouchableOpacity, StyleSheet, Modal, ActivityIndicator,
  SafeAreaView, Platform,
} from 'react-native'
import { Camera, BarCodeScanningResult } from 'expo-camera'
import { CameraIcon, CloseIcon } from './Icons'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#000', text: '#1A1A1A', textSecondary: '#666666',
}

interface BarcodeScannerProps {
  /** 是否显示扫码界面 */
  visible: boolean
  /** 扫码成功回调（返回条码内容） */
  onScan: (barcode: string) => void
  /** 关闭扫码界面 */
  onClose: () => void
  /** 标题文字 */
  title?: string
}

/**
 * BarcodeScanner — 可复用摄像头扫码组件
 *
 * 功能：
 * 1. 调用设备摄像头/PDA 扫码头进行条码识别
 * 2. 支持一维码（EAN-13, Code128, Code39, UPC-A 等）和二维码 QR
 * 3. 扫码成功后自动触发回调并关闭
 * 4. 手动关闭通过 onClose 回调
 *
 * 使用示例：
 * ```tsx
 * <BarcodeScanner
 *   visible={showScanner}
 *   onScan={(barcode) => { setBarcode(barcode); handleSubmit() }}
 *   onClose={() => setShowScanner(false)}
 *   title="扫码入库"
 * />
 * ```
 */
export default function BarcodeScanner({
  visible,
  onScan,
  onClose,
  title = '扫码',
}: BarcodeScannerProps) {
  const [hasPermission, setHasPermission] = useState<boolean | null>(null)
  const [scanned, setScanned] = useState(false)

  // 请求摄像头权限
  useEffect(() => {
    if (visible) {
      ;(async () => {
        try {
          // 使用 expo-camera 的权限 API
          const { status } = await Camera.requestCameraPermissionsAsync()
          setHasPermission(status === 'granted')
        } catch {
          setHasPermission(false)
        }
      })()
    }
  }, [visible])

  // 条码扫描回调
  const handleBarCodeScanned = useCallback(
    (result: BarCodeScanningResult) => {
      if (scanned) return // 防止重复扫描
      setScanned(true)
      const barcode = result.data
      // 触发回调并关闭扫码界面
      onScan(barcode)
    },
    [scanned, onScan]
  )

  // 重新开始扫码（关闭后重新打开时重置）
  useEffect(() => {
    if (visible) {
      setScanned(false)
    }
  }, [visible])

  // 渲染扫码界面
  const renderScanner = () => {
    if (hasPermission === null) {
      return (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.permissionText}>正在请求摄像头权限...</Text>
        </View>
      )
    }

    if (hasPermission === false) {
      return (
        <View style={styles.centerContainer}>
          <CameraIcon size={64} color="#ccc" />
          <Text style={styles.permissionTitle}>无法访问摄像头</Text>
          <Text style={styles.permissionText}>
            请在系统设置中允许本应用使用摄像头权限
          </Text>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <Text style={styles.closeButtonText}>关闭</Text>
          </TouchableOpacity>
        </View>
      )
    }

    return (
      <View style={styles.cameraContainer}>
        <Camera
          style={styles.camera}
          type={Camera.Constants.Type.back}
          onBarCodeScanned={handleBarCodeScanned}
          barCodeScannerSettings={{
            barCodeTypes: [
              'qr',
              'ean13', 'ean8',
              'code128', 'code39', 'code93',
              'upc_e', 'upc_a',
              'itf14',
              'pdf417',
              'datamatrix',
              'aztec',
              'codabar',
            ],
          }}
        >
          {/* 扫描框 UI 叠加层 */}
          <View style={styles.scanOverlay}>
            {/* 顶部标题栏 */}
            <SafeAreaView style={styles.topBar}>
              <View style={styles.topBarContent}>
                <Text style={styles.topBarTitle}>{title}</Text>
                <TouchableOpacity style={styles.topBarClose} onPress={onClose}>
                  <CloseIcon size={20} color="#fff" />
                </TouchableOpacity>
              </View>
            </SafeAreaView>

            {/* 扫描框 */}
            <View style={styles.scanFrameContainer}>
              <View style={styles.scanFrame}>
                {/* 四角装饰 */}
                <View style={[styles.corner, styles.cornerTL]} />
                <View style={[styles.corner, styles.cornerTR]} />
                <View style={[styles.corner, styles.cornerBL]} />
                <View style={[styles.corner, styles.cornerBR]} />
                {/* 扫描线动画 */}
                <View style={styles.scanLine} />
              </View>
              <Text style={styles.scanHint}>将条码对准框内自动扫描</Text>
            </View>

            {/* 底部手动输入按钮 */}
            <View style={styles.bottomBar}>
              <TouchableOpacity style={styles.manualInputBtn} onPress={onClose}>
                <Text style={styles.manualInputText}>手动输入条码</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Camera>
      </View>
    )
  }

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={onClose}
    >
      <View style={styles.container}>{renderScanner()}</View>
    </Modal>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bg,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
    padding: 32,
  },
  permissionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: Colors.text,
    marginBottom: 8,
  },
  permissionText: {
    fontSize: 15,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  closeButton: {
    marginTop: 24,
    paddingHorizontal: 32,
    paddingVertical: 14,
    backgroundColor: Colors.primary,
    borderRadius: 8,
  },
  closeButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },

  // ── 摄像头区域 ──
  cameraContainer: {
    flex: 1,
  },
  camera: {
    flex: 1,
  },

  // ── 扫描叠加层 ──
  scanOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.3)',
    justifyContent: 'space-between',
  },

  // ── 顶部栏 ──
  topBar: {
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  topBarContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  topBarTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  topBarClose: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  // topBarCloseText removed — using CloseIcon SVG

  // ── 扫描框 ──
  scanFrameContainer: {
    alignItems: 'center',
  },
  scanFrame: {
    width: 280,
    height: 200,
    position: 'relative',
    overflow: 'hidden',
  },
  corner: {
    position: 'absolute',
    width: 24,
    height: 24,
    borderColor: '#00FF88',
  },
  cornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: 4,
    borderLeftWidth: 4,
  },
  cornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: 4,
    borderRightWidth: 4,
  },
  cornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
  },
  cornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 4,
    borderRightWidth: 4,
  },
  scanLine: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 2,
    backgroundColor: '#00FF88',
    top: 20,
    shadowColor: '#00FF88',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 8,
    elevation: 4,
  },
  scanHint: {
    color: '#fff',
    fontSize: 14,
    marginTop: 16,
    textAlign: 'center',
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },

  // ── 底部栏 ──
  bottomBar: {
    alignItems: 'center',
    paddingBottom: Platform.OS === 'ios' ? 40 : 24,
  },
  manualInputBtn: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: 'rgba(255,255,255,0.2)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.4)',
  },
  manualInputText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
})
