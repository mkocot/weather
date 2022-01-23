// fake nodemcu
module nodemcu() {
color("gray", 0.5)
cube([57, 30, 13]);
}

//fake battery
module battery() {
color("gray", 0.5)
    cube([70, 65, 23]);
}

module bmp280() {
    color("purple", 0.5)
    cube([14, 10, 5]);
}

nodemcu();
battery();
bmp280();