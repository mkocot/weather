include<nodemcu.scad>
tolerance = 0.2;
$fn = 40;
node_offset = 15;
bat = [70, 70, 25];

function center(a, b) = (a - b)/2;

//cube([nodemcu_bb.x, nodemcu_bb.y, 1]);

//color("blue")
//cube([nodemcu_bb.x, nodemcu_bb.y, 1]);


// OUTER size
slide_height = 3;

size = [100, 50, node_offset + nodemcu_bb.z + tolerance + 0.5 + slide_height/2 + 2];
slide_size = [size.x, size.y -2, slide_height];
echo (size=size);
inset = [2, 2, 2];

difference() 
{
cube(size);
  
color("yellow")
translate(inset)
cube(size + 2*[inset.x, -inset.y, inset.z]);
  
  // TOP cap
  translate([inset.x, inset.y/2, node_offset + nodemcu_bb.z + tolerance + 0.5])
  {
    color("red")
  translate([0, -0.5, 0])
  slid([slide_size.x, slide_size.y+1, slide_size.z+0.5], 2 + 0.5);
  }
  // SIDE CAP
  translate([size.x - 4, inset.y/2, inset.z])
rotate([0, 270, 0])
  {
    color("red")
  translate([0, -0.5, 0])
  slid([size.z, slide_size.y+1, slide_size.z+0.5], 2 + 0.5);
  }
}

  
  
// cpu holder pilars
// 15 - arbitralnie wybrany offset "aby zmieścić kable"

pillar_size = [5, nodemcu_bb.y, pins.z - tolerance + node_offset];
translate([10, center(size, nodemcu_bb).y,0]) {
  for (i = [0:3]) {
  translate(holes[i] + [0, 0, pillar_size.z - 1])
        cylinder(h = cpu.z, d = 2);
  }

  color("purple")
  translate([0, center(nodemcu_bb, pillar_size).y, 0]) {
  cube(pillar_size);
    translate([nodemcu_bb.x - pillar_size.x, 0, 0])
    cube(pillar_size);
  }
  
  
  translate([0, 0, node_offset])
  nodemcu();
}



module slid(size, offset = 0) {
  // offset how much we remove from both sides
  // eg. offset = 1
  // top size = size - offset*2
  hull() {
    translate([0, offset, size.z-1])
    linear_extrude(1)
    square([size.x, size.y - offset*2 + 0.0001]);

    // bottom should be as small as possible
    linear_extrude(0.0001)
    square([size.x, size.y]);
  }
  // cut holes
}



module rounded_hole(size) {
  translate([size.x/2, size.x/2, 0])
linear_extrude(size.z)
hull() {
circle(d = size.x);
translate([0, size.y - size.x, 0])
circle(d = size.x);
}
}

if (0) {
// slid at height
translate([inset.x, 1, node_offset + nodemcu_bb.z + tolerance + 0.5])
{
difference() {
slid(slide_size, 2);
for (j = [0:3]) {
for (i = [0:17]) {
translate([10 + i*4.8, 4 + j*9, -4])
rotate([0, 0, 45])
rounded_hole([1, 10, 10]);
}
}
}
// slightly higher and wider
 // color("red", 0.5)
 // translate([0, -0.5, 0])
//  slid([slide_size.x, slide_size.y+1, slide_size.z+0.5], 2 + 0.5);
}
}


// battery
c1 = center(size, bat);
translate([c1.x*2, c1.y, -bat.z])
cube(bat);