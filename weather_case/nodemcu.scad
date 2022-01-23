// fake nodemcu
// pins + cpu = 13mm
// borad
nodemcu_board = [57, 31.1, 1.6]; //
pins = [38, 2.5, 8.2];
cpu = [24, 16, 9 - nodemcu_board.z];
nodemcu_bb = nodemcu_board + [0, 0, cpu.z + pins.z];
hole = [3, nodemcu_board.z];
holes = [
[hole.x/2, hole.x/2, 0] + [1, 1, 0],
[-hole.x/2, hole.x/2, 0] + [nodemcu_board.x - 1, 1, 0],
[-hole.x/2, -hole.x/2, 0] + [nodemcu_board.x - 1, nodemcu_board.y - 1, 0],
[hole.x/2, -hole.x/2, 0] + [1, nodemcu_board.y - 1, 0]
];
module nodemcu() {
  translate([0, 0, pins.z + nodemcu_board.z ] - nodemcu_bb/2)
  mirror([0, 0, 1]) {
    difference() {
      union() {
    // board
    cube(nodemcu_board);
    translate([0, 0, nodemcu_board.z]) {
    // fake pins row
    color("black")
        translate([(nodemcu_board.x - pins.x)/2, 0, 0])
    cube(pins);
    // fake holes
    color("black")
        translate([(nodemcu_board.x - pins.x)/2, nodemcu_board.y - pins.y, 0])
    cube(pins);
    }
    // fake cpu
    color("red")
    translate([0, (nodemcu_board.y - cpu.y)/2, - cpu.z])
    cube(cpu);
  }
  union() {
    // mount holes

    for (i = [0:3]) {
      translate(holes[i] - [0, 0, 0.01])
    cylinder(h = hole.y + 0.02, d = hole.x);
    }
  }
}

  // usb thing
  usb = [5, 5, 3];
  usb_depth = 5;
  color("gray")
  translate([nodemcu_board.x - usb.x, 0, -nodemcu_board.z - usb.z/2])
  translate([0, nodemcu_board.y - usb.y, 0]/2)
  cube([5, 5, 3]);
  }
}
module nodemcu_simple() {
    color("pink", 0.4)
    cube(nodemcu_bb);
}
//nodemcu();
//nodemcu_simple();