import React from 'react'
import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { StatusBar } from 'expo-status-bar'

import LoginScreen from './screens/LoginScreen'
import InboundScreen from './screens/InboundScreen'
import OutboundScreen from './screens/OutboundScreen'
import RestockScreen from './screens/RestockScreen'
import TrackingScreen from './screens/TrackingScreen'
import { useAuthStore } from './store/authStore'

export type RootStackParamList = {
  Login: undefined
  Inbound: undefined
  Outbound: undefined
  Restock: undefined
  Tracking: undefined
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
          headerStyle: { backgroundColor: '#1890ff' },
          headerTintColor: '#fff',
          headerTitleStyle: { fontWeight: 'bold' },
        }}
      >
        {token ? (
          <>
            <Stack.Screen
              name="Inbound"
              component={InboundScreen}
              options={{ title: `入库 (${user?.username || ''})` }}
            />
            <Stack.Screen
              name="Outbound"
              component={OutboundScreen}
              options={{ title: '出库' }}
            />
            <Stack.Screen
              name="Restock"
              component={RestockScreen}
              options={{ title: '补料上架' }}
            />
            <Stack.Screen
              name="Tracking"
              component={TrackingScreen}
              options={{ title: '库存跟踪' }}
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
