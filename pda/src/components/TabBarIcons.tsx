import React from 'react'
import Svg, { Path, G, Rect } from 'react-native-svg'

type Props = {
  focused: boolean
  color: string
  size: number
}

export function InboundIcon({ focused, color, size }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <G stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <Rect x="3" y="10" width="18" height="11" rx="2" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Path d="M12 3v10" />
        <Path d="m8 9 4 4 4-4" />
      </G>
    </Svg>
  )
}

export function ShelvingIcon({ focused, color, size }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <G stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <Rect x="2" y="3" width="20" height="4" rx="1" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Rect x="2" y="10" width="20" height="4" rx="1" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Rect x="2" y="17" width="20" height="4" rx="1" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Path d="M8 3v4M16 3v4M8 10v4M16 10v4M8 17v4M16 17v4" stroke={color} strokeWidth={1.2} />
      </G>
    </Svg>
  )
}

export function OutboundIcon({ focused, color, size }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <G stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <Rect x="3" y="2" width="6" height="6" rx="1" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Rect x="12" y="2" width="9" height="2" rx="0.5" />
        <Rect x="12" y="6" width="9" height="2" rx="0.5" />
        <Rect x="2" y="12" width="6" height="6" rx="1" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Rect x="12" y="12" width="9" height="2" rx="0.5" />
        <Rect x="12" y="16" width="9" height="2" rx="0.5" />
        <Rect x="2" y="22" width="6" height="2" rx="0.5" />
      </G>
    </Svg>
  )
}

export function TrackingIcon({ focused, color, size }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <G stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <Path d="M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14z" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Path d="m21 21-4.65-4.65" />
        <Path d="M10 7v3l2 1" strokeWidth={1.6} />
      </G>
    </Svg>
  )
}

export function HomeIcon({ focused, color, size }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <G stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <Path d="M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0z" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Path d="M12 8v8M8 12h8" strokeWidth={2} />
      </G>
    </Svg>
  )
}

export function SettingsIcon({ focused, color, size }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <G stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <Path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" stroke={color} fill={focused ? color : 'none'} fillOpacity={focused ? 0.15 : 0} />
        <Path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </G>
    </Svg>
  )
}
