import pytest
from app.quality import protect, restore, check, segment

@pytest.mark.parametrize('text',[
    'Power supply voltage: 12 VDC.',
    'Connect J3 to the STM32F407 control board.',
    'Maximum torque is 4.5 Nm.',
    'Use the M4x20 screws.',
    'Communication uses CAN and RS-485.',
    'ISO 9001, RoHS, REACH, -2.5 V and 12 VDC twice: 12 VDC.',
])
def test_roundtrip(text):
    protected,mapping=protect(text)
    assert restore(protected,mapping)==text
    assert not check(text,restore(protected,mapping))

def test_glossary_multiword():
    text,mapping=protect('The power supply feeds the housing.',{'power supply':'alimentation','housing':'boîtier'})
    assert restore(text,mapping)=='The alimentation feeds the boîtier.'

@pytest.mark.parametrize('kind',['missing','duplicated'])
def test_placeholder_damage_fails(kind):
    text,mapping=protect('Connect J3.')
    token=next(iter(mapping))
    damaged=text.replace(token,'') if kind=='missing' else text+token
    with pytest.raises(ValueError): restore(damaged,mapping)

@pytest.mark.parametrize('target',['Voltage: 24 VDC.','Voltage: -12 VDC.','Voltage: 12 VAC.','Voltage: 12 VDC and 3.'])
def test_changed_technical_data(target): assert check('Voltage: 12 VDC.',target)

def test_segmentation_keeps_decimal():
    assert segment('Torque is 4.5 Nm. Connect J3.',20)==['Torque is 4.5 Nm.','Connect J3.']



def test_decimal_comma_preserves_technical_value():
    assert not check('1.2 MHz and 41.8 km', '1,2 MHz et 41,8 km')
    assert check('1.2 MHz', '1,3 MHz')
