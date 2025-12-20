# Magic Caster BLE

Python library to interact with the discontinued HP Magic Caster Wands via BLE. Used in the [HA-Magic-Caster custom component](https://github.com/TeamRECaster/ha-magic-caster).

## Features

* Automagically discovers devices
* Detects cast spells
  * Limited to the 5 pre-programmed spells each wand is capable of independent of the discontinued app. See start of [this video](https://www.youtube.com/watch?v=fE2W8WKQXa0) & test with your box to see available spell states!
  * Further spell interpretation (>70) can be restored without the app, but the required resources will not be included in this library for copyright reasons.
* Reports battery level

### To be supported

* Expose further wand configuration
* Write interactions to wand
  * Pre-programmed spells use the default "payoff"; writing is useful for the extra spells mentioned in [#features](#features)
* Wand Box support
* tbd.

## Usage

See `examples/` dir
