import React from 'react'
import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { StatusBar } from 'expo-status-bar'

import LoginScreen from './screens/LoginScreen'
import HomeScreen from './screens/HomeScreen'
import InboundScreen from './screens/InboundScreen'
import ShelvingScreen from './screens/ShelvingScreen'
import OutboundScreen from './screens/OutboundScreen'
import TrackingScreen from './screens/TrackingScreen'
import SettingsScreen from './screens/SettingsScreen'
import { useAuthStore } from './store/authStore'

export type RootStackParamList = {
  Login: undefined
  Home: undefined
  Inbound: undefined
  Shelving: undefined
  Outbound: undefined
  Tracking: undefined
  Settings: undefined
}

const Stack = createNativeStackNavigator<RootStackParamList>()

export default function App() {
  const token = useAuthStore((s) => s.token)
  const user = useAuthStore((s) => s.user)

  return (
    <NavigationContainer>
      <StatusBar style="auto" />
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: '#0066CC' },
          headerTintColor: '#fff',
          headerTitleStyle: { fontWeight: 'bold', fontSize: 20 },
          headerBackTitleVisible: false,
        }}
      >
        {token ? (
          <>
            <Stack.Screen
              name="Home"
              component={HomeScreen}
              options={{ title: '智能物料管理系统', headerShown: false }}
            />
            <Stack.Screen
              name="Inbound"
              component={InboundScreen}
              options={{ title: '收料入库' }}
            />
            <Stack.Screen
              name="Shelving"
              component={ShelvingScreen}
              options={{ title: '料盘上架' }}
            />
            <Stack.Screen
              name="Outbound"
              component={OutboundScreen}
              options={{ title: '扫码出库' }}
            />
            <Stack.Screen
              name="Tracking"
              component={TrackingScreen}
              options={{ title: '库存跟踪' }}
            />
            <Stack.Screen
              name="Settings"
              component={SettingsScreen}
              options={{ title: '设置' }}
            />
          </>
        ) : (
          <Stack.Screen
            name="Login"
            component={LoginScreen}
            options={{ headerShown: false }}
          />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  )
}
