import React from 'react'
import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { StatusBar } from 'expo-status-bar'

import { LoginScreen } from './screens/LoginScreen'
import { InboundScreen } from './screens/InboundScreen'
import { OutboundScreen } from './screens/OutboundScreen'
import { RestockScreen } from './screens/RestockScreen'
import { TrackingScreen } from './screens/TrackingScreen'
import { useAuthStore } from './store/authStore'

const Stack = createNativeStackNavigator()

export default function App() {
  const { token } = useAuthStore()

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
            <Stack.Screen name="Inbound" component={InboundScreen} />
            <Stack.Screen name="Outbound" component={OutboundScreen} />
            <Stack.Screen name="Restock" component={RestockScreen} />
            <Stack.Screen name="Tracking" component={TrackingScreen} />
          </>
        ) : (
          <Stack.Screen name="Login" component={LoginScreen} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  )
}
